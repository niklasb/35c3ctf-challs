#pragma once

#include <string>
#include <sstream>
#include <memory>

#include "sqlengine.h"

namespace pwndb {

using Condition = std::unique_ptr<SqlSelector>;

namespace parser {

struct Parser {
  const char* str;
  uint64_t size;
  void inc() { str++; size--; }
};

template <typename T>
struct Result {
  T value;
  Parser rest;
  bool valid;
};

struct Unit {};

#define BINDP(f, ...) ([&](parser::Parser p) { return f(__VA_ARGS__, p); })
#define SKIP(R, f) { auto next = f(p); \
                     if (!next.valid) return parser::invalid<R>(); \
                     p = next.rest; }
#define SUB(R, x, f) decltype(f(p).value) x; \
                     { auto next = f(p); \
                       if (!next.valid) return parser::invalid<R>(); \
                       p = next.rest; x = std::move(next.value); }
#define SUB_OPT(R, x, f) \
                     { auto next = f(p); \
                       if (next.valid) { \
                         p = next.rest; x = std::move(next.value); }}

template <typename T>
Result<T> invalid() {
  return Result<T> { T(), Parser{nullptr, 0}, false };
}

template <typename T>
Result<T> valid(T x, Parser rest) {
  return Result<T> { std::move(x), rest, true };
}

template <typename F>
Result<std::string> take_while(F pred, Parser p) {
  std::string res;
  while (p.size && pred(*p.str)) {
    res += *p.str;
    p.inc();
  }
  return valid(res, p);
}

template <typename F>
Result<std::string> take_while1(F pred, Parser p) {
  auto res = take_while(pred, p);
  return res.value.empty() ? invalid<std::string>() : res;
}

Result<std::string> whitespace(Parser p) {
  return take_while1(isspace, p);
}

Result<std::string> maybe_whitespace(Parser p) {
  return take_while(isspace, p);
}

Result<std::string> fixed(size_t len, Parser p) {
  if (p.size < len)
    return invalid<std::string>();
  std::string res(p.str, p.str + len);
  p.size -= len;
  p.str += len;
  return valid<std::string>(res, p);
}

Result<std::string> char_(Parser p) {
  return fixed(1, p);
}

Result<Unit> exact(std::string s, Parser p) {
  if (p.size < s.size())
    return invalid<Unit>();
  for (size_t i = 0; i < s.size(); ++i) {
    if (tolower(*p.str) != tolower(s[i]))
      return invalid<Unit>();
    p.inc();
  }
  return valid(Unit(), p);
}

template <typename L, typename R>
auto right(L left, R right, Parser p) {
  using T = decltype(right(p).value);
  SKIP(T, left);
  return right(p);
}

template <typename L, typename R>
auto left(L left, R right, Parser p) {
  using T = decltype(left(p).value);
  SUB(T, res, left);
  SKIP(T, right);
  return valid<T>(std::move(res), p);
}

template <typename L, typename R>
Result<Unit> both(L left, R right, Parser p) {
  SKIP(Unit, left);
  SKIP(Unit, right);
  return valid<Unit>(Unit(), p);
}

template <typename L, typename R, typename X>
auto middle(L left, X inner, R right, Parser p) {
  using T = decltype(inner(p).value);
  SKIP(T, left);
  SUB(T, res, inner);
  SKIP(T, right);
  return valid<T>(std::move(res), p);
}

template <typename L, typename R>
auto either(L left, R right, Parser p) {
  auto res1 = left(p);
  if (res1.valid)
    return res1;
  return right(p);
}

template <typename F>
auto eval(const std::string& input, F f) {
  return f(Parser { input.c_str(), input.size() });
}

Result<std::string> identifier(Parser p) {
  return take_while1([](char x) { return isalpha(x) || x == '_'; }, p);
}

Result<Condition> term(Parser p);
Result<Condition> and_term(Parser p);
Result<Condition> or_term(Parser p);

template <typename F>
Result<std::string> quoted_string(char delim, F esc, Parser p) {
  SKIP(std::string, BINDP(exact, std::string(1, delim)));
  std::string s;
  while (p.size && *p.str != delim) {
    if (*p.str == '\\') {
      p.inc();
      SUB(std::string, subst, esc);
      s += subst;
    } else {
      s += *p.str;
      p.inc();
    }
  }
  SKIP(std::string, BINDP(exact, std::string(1, delim)));
  return valid(s, p);
}

Result<std::string> single_quoted_string(Parser p) {
  return quoted_string('\'', char_, p);
}

int tohex(char c) {
  if ('0' <= c && c <= '9') return c - '0';
  if ('a' <= c && c <= 'f') return c - 'a' + 10;
  if ('A' <= c && c <= 'F') return c - 'A' + 10;
  return -1;
}

Result<std::string> double_quoted_string(Parser p) {
  using namespace std;
  auto esc = [](Parser p) {
    SUB(std::string, c, char_);
    switch (c[0]) {
      case 'n':
        c = "\n";
        break;
      case 't':
        c = "\t";
        break;
      case 'r':
        c = "\r";
        break;
      case 'b':
        c = "\b";
        break;
      case 'x':
        if (p.size < 2)
          return invalid<std::string>();
        int a = tohex(p.str[0]), b = tohex(p.str[1]);
        if (a < 0 || b < 0)
          return invalid<std::string>();
        c[0] = a*0x10 + b;
        p.size -= 2;
        p.str += 2;
        break;
    }
    return valid<std::string>(c, p);
  };
  return quoted_string('"', esc, p);
}

Result<std::string> string_literal(Parser p) {
  return either(single_quoted_string, double_quoted_string, p);
}

Result<Condition> term(Parser p) {
  using namespace std;
  auto res = middle(
      BINDP(both, maybe_whitespace, BINDP(exact, "(")),
      or_term,
      BINDP(both, maybe_whitespace, BINDP(exact, ")")),
      p);
  if (res.valid)
    return res;

  SKIP(Condition, maybe_whitespace);
  SUB(Condition, column, identifier);
  SKIP(Condition, maybe_whitespace);
  SKIP(Condition, BINDP(exact, "="));
  SKIP(Condition, maybe_whitespace);
  SUB(Condition, value, string_literal);

  Condition term = std::make_unique<SqlSelectorTerm>(
        column, Border(value, true), Border(value, true));
  return valid(std::move(term), p);
}

Result<Condition> and_term(Parser p) {
  using namespace std;
  SUB(Condition, left, term);

  auto extra = [](Parser p) {
    SKIP(Condition, maybe_whitespace);
    SKIP(Condition, BINDP(exact, "and"));
    return and_term(p);
  };

  auto res = extra(p);
  if (res.valid) {
    Condition term = std::make_unique<SqlSelectorAnd>(
        std::move(left), std::move(res.value));
    return valid(std::move(term), res.rest);
  } else {
    return valid(std::move(left), p);
  }
}

Result<Condition> or_term(Parser p) {
  SUB(Condition, left, and_term);

  auto extra = [](Parser p) {
    SKIP(Condition, whitespace);
    SKIP(Condition, BINDP(exact, "or"));
    return or_term(p);
  };

  auto res = extra(p);
  if (res.valid) {
    Condition term = std::make_unique<SqlSelectorOr>(
        std::move(left), std::move(res.value));
    return valid(std::move(term), res.rest);
  } else {
    return valid(std::move(left), p);
  }
}

Result<Condition> where_clause(Parser p) {
  SKIP(Condition, whitespace)
  SKIP(Condition, BINDP(exact,"where"));
  SKIP(Condition, whitespace);
  return or_term(p);
}

Result<Unit> statement_end(Parser p) {
  return either(BINDP(exact, ";"),
                BINDP(either, BINDP(exact, "#"), BINDP(exact, "-- ")), p);
}

Result<SqlSelect> sql_select(Parser p) {
  SKIP(SqlSelect, maybe_whitespace);
  SKIP(SqlSelect, BINDP(exact,"select"));
  SKIP(SqlSelect, maybe_whitespace);
  SKIP(SqlSelect, BINDP(exact,"*"));
  SKIP(SqlSelect, maybe_whitespace);
  SKIP(SqlSelect, BINDP(exact,"from"));
  SKIP(SqlSelect, whitespace);
  SUB(SqlSelect, table_name, identifier);

  Condition sel = std::make_unique<SqlSelectorAll>();
  SUB_OPT(SqlSelect, sel, where_clause);

  SKIP(SqlSelect, maybe_whitespace);
  SKIP(SqlSelect, statement_end);

  return valid<SqlSelect>(SqlSelect { table_name, std::move(sel) }, p);
}

template <typename F>
auto tuple(F piece, Parser p) {
  using T = decltype(piece(p).value);
  using R = std::vector<T>;

  SKIP(R, BINDP(exact,"("));

  R res;
  while (1) {
    SKIP(R, maybe_whitespace);
    SUB(R, val, piece);
    SKIP(R, maybe_whitespace);
    SUB(R, c, char_);
    res.push_back(std::move(val));
    if (c == ",")
      continue;
    if (c == ")")
      break;
    return invalid<R>();
  }
  return valid(res, p);
}

Result<SqlInsert> sql_insert(Parser p) {
  using namespace std;
  SKIP(SqlInsert, maybe_whitespace);
  SKIP(SqlInsert, BINDP(exact,"insert"));
  SKIP(SqlInsert, whitespace);
  SKIP(SqlInsert, BINDP(exact,"into"));
  SKIP(SqlInsert, whitespace);
  SUB(SqlInsert, table_name, identifier);
  SKIP(SqlInsert, maybe_whitespace);

  auto res = tuple(identifier, p);
  if (!res.valid) return invalid<SqlInsert>();
  p = res.rest;
  auto columns = res.value;

  SKIP(SqlInsert, maybe_whitespace);
  SKIP(SqlInsert, BINDP(exact,"values"));

  std::vector<std::vector<std::string>> values;
  while (1) {
    SKIP(SqlInsert, maybe_whitespace);

    auto res = tuple(string_literal, p);
    if (!res.valid) break;
    p = res.rest;
    values.push_back(std::move(res.value));

    SKIP(SqlInsert, maybe_whitespace);
    if (p.size && p.str[0] == ',') {
      p.inc();
      continue;
    } else {
      break;
    }
  }

  SKIP(SqlInsert, maybe_whitespace);
  SKIP(SqlInsert, statement_end);

  return valid<SqlInsert>(
          SqlInsert { table_name, std::move(columns), std::move(values) }, p);
}

Result<SqlCreateTable> sql_create_table(Parser p) {
  using namespace std;
  SKIP(SqlCreateTable, maybe_whitespace);
  SKIP(SqlCreateTable, BINDP(exact,"create"));
  SKIP(SqlCreateTable, whitespace);
  SKIP(SqlCreateTable, BINDP(exact,"table"));
  SKIP(SqlCreateTable, whitespace);
  SUB(SqlCreateTable, table_name, identifier);
  SKIP(SqlCreateTable, maybe_whitespace);

  auto res = tuple(identifier, p);
  if (!res.valid) return invalid<SqlCreateTable>();
  p = res.rest;
  auto columns = res.value;

  SKIP(SqlCreateTable, maybe_whitespace);
  SKIP(SqlCreateTable, statement_end);

  return valid<SqlCreateTable>(
          SqlCreateTable { table_name, std::move(columns) }, p);
}

Result<int> number(Parser p) {
  auto res = take_while1([](char c) { return isdigit(c); }, p);
  if (!res.valid) return invalid<int>();
  p = res.rest;
  auto num = res.value;
  std::stringstream ss;
  ss << num;
  int x;
  ss >> x;
  return valid(x, p);
}

Result<int> advance_cursor(Parser p) {
  using namespace std;
  SKIP(int, maybe_whitespace);
  SKIP(int, BINDP(exact,"advance"));
  SKIP(int, whitespace);
  SKIP(int, BINDP(exact,"cursor"));
  SKIP(int, whitespace);

  SUB(int, cursor_id, number);

  SKIP(int, maybe_whitespace);
  SKIP(int, statement_end);

  return valid(cursor_id, p);
}

Result<int> get_cursor(Parser p) {
  using namespace std;
  SKIP(int, maybe_whitespace);
  SKIP(int, BINDP(exact,"get"));
  SKIP(int, whitespace);
  SKIP(int, BINDP(exact,"cursor"));
  SKIP(int, whitespace);

  SUB(int, cursor_id, number);

  SKIP(int, maybe_whitespace);
  SKIP(int, statement_end);

  return valid(cursor_id, p);
}

Result<SqlUpdate> update_cursor(Parser p) {
  using namespace std;
  SKIP(SqlUpdate, maybe_whitespace);
  SKIP(SqlUpdate, BINDP(exact,"update"));
  SKIP(SqlUpdate, whitespace);
  SKIP(SqlUpdate, BINDP(exact,"cursor"));
  SKIP(SqlUpdate, whitespace);
  SUB(SqlUpdate, cursor_id, number);
  SKIP(SqlUpdate, whitespace);
  SKIP(SqlUpdate, BINDP(exact,"set"));
  SKIP(SqlUpdate, whitespace);

  std::vector<std::string> columns, values;
  while (1) {
    SKIP(SqlUpdate, maybe_whitespace);
    SUB(SqlUpdate, column, identifier);
    SKIP(SqlUpdate, maybe_whitespace);
    SKIP(SqlUpdate, BINDP(exact,"="));
    SKIP(SqlUpdate, maybe_whitespace);
    SUB(SqlUpdate, value, string_literal);
    SKIP(SqlUpdate, maybe_whitespace);

    columns.push_back(std::move(column));
    values.push_back(std::move(value));
    if (p.size && p.str[0] == ',') {
      p.inc();
      continue;
    } else {
      break;
    }
  }

  SKIP(SqlUpdate, maybe_whitespace);
  SKIP(SqlUpdate, statement_end);

  return valid(SqlUpdate { cursor_id, columns, values }, p);
}

}
}
