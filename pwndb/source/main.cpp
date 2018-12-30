#include <iostream>
#include <iomanip>
#include <fstream>

#include "sstable.h"
#include "sqlengine.h"
#include "sqlparser.h"

using namespace pwndb;
using namespace std;

#define TESTS 0

#if TESTS
void debug_selector(const SqlSelector* c, int ind=0) {
  for (int i = 0; i < ind; ++i) cout << "  ";
  switch (c->type()) {
    case SqlSelectorType::ALL: {
      cout << "ALL" << endl;
      return;
    }
    case SqlSelectorType::TERM: {
      const auto* sel = dynamic_cast<const SqlSelectorTerm*>(c);
      cout << sel->column << " in [" << sel->lo.bound << ", " << sel->hi.bound << "]" << endl;
      return;
    }
    case SqlSelectorType::AND: {
      const auto* sel = dynamic_cast<const SqlSelectorAnd*>(c);
      cout << "AND" << endl;
      debug_selector(sel->a.get(), ind+1);
      debug_selector(sel->b.get(), ind+1);
      return;
    }
    case SqlSelectorType::OR: {
      const auto* sel = dynamic_cast<const SqlSelectorOr*>(c);
      cout << "OR" << endl;
      debug_selector(sel->a.get(), ind+1);
      debug_selector(sel->b.get(), ind+1);
      return;
    }
    default: assert(0);
  }
}

void parser_tests() {
  using namespace std;
  {
    auto res = parser::eval("    (    ", [](parser::Parser p) {
          return parser::middle(
              parser::maybe_whitespace,
              BINDP(parser::exact, "("),
              parser::maybe_whitespace,
              p);
        });
    assert(res.valid);
  }
  {
    string inp = "    foo  bar  ";
    auto pa = [](parser::Parser p) {
      SKIP(std::string, parser::whitespace);
      return parser::identifier(p);
    };
    auto res = parser::eval(inp, pa);
    assert(res.valid);
  }
  {
    auto res = parser::eval("'foo\\z\\\\b\\n\\xff ar\\'a\\\"sd'", parser::single_quoted_string);
    assert(res.valid);
    assert(res.value == "fooz\\bnxff ar\'a\"sd");
    assert(res.rest.size==0);
  }
  {
    auto res = parser::eval("\"\\x01-foo\\z\\\\b\\n\\xff ar\\'a\\\"sd\"", parser::double_quoted_string);
    assert(res.valid);
    assert(res.value == "\x01-fooz\\b\n\xff ar\'a\"sd");
    assert(res.rest.size==0);
  }
  {
    auto res = parser::eval("\"abc\"", parser::string_literal);
    assert(res.valid);
    assert(res.value == "abc");
    assert(res.rest.size==0);
  }
  {
    auto res = parser::eval("'abc'", parser::string_literal);
    assert(res.valid);
    assert(res.value == "abc");
    assert(res.rest.size==0);
  }
  {
    string inp = "((a='b' or c='d') and e='f' or d='g') and (f='g' or foo='bar')";
    auto res = parser::eval(inp, parser::or_term);
    assert(res.valid);
    assert(res.rest.size==0);
    //debug_selector(res.value.get());
  }
  {
    string inp = "((a='b') and (c='d'))";
    auto res = parser::eval(inp, parser::or_term);
    assert(res.valid);
    assert(res.rest.size==0);
  }
  {
    auto res = parser::eval("  select * from xxxx ; ", parser::sql_select);
    assert(res.valid);
    assert(res.value.table_name == "xxxx");
  }
  {
    auto res = parser::eval("  select * from xxxx where a='b' and c='d' # ", parser::sql_select);
    assert(res.valid);
    assert(res.value.table_name == "xxxx");
    //debug_selector(res.value.selector.get());
  }
  {
    auto res = parser::eval("  insert into xxxx (a, b, c ) values ('aa', 'bb'); ", parser::sql_insert);
    assert(res.valid);
    assert(res.value.table_name == "xxxx");
    assert((res.value.columns == std::vector<std::string>{"a", "b", "c"}));
    assert((res.value.values == std::vector<std::vector<std::string>>{{"aa", "bb"}}));
    //debug_selector(res.value.selector.get());
  }
  {
    auto res = parser::eval("  insert into xxxx (a, b, c ) values ('aa', 'bb'), ('d'); ", parser::sql_insert);
    assert(res.valid);
    assert(res.value.table_name == "xxxx");
    assert((res.value.columns == std::vector<std::string>{"a", "b", "c"}));
    assert((res.value.values == std::vector<std::vector<std::string>>{{"aa", "bb"}, {"d"}}));
    //debug_selector(res.value.selector.get());
  }
  {
    auto res = parser::eval("  create table xxxx (a, b, c ) ; ", parser::sql_create_table);
    assert(res.valid);
    assert(res.value.table_name == "xxxx");
    assert((res.value.columns == std::vector<std::string>{"a", "b", "c"}));
    //debug_selector(res.value.selector.get());
  }
  {
    auto res = parser::eval("  get cursor 1337 ; ", parser::get_cursor);
    assert(res.valid);
    assert(res.value == 1337);
    //debug_selector(res.value.selector.get());
  }
  {
    auto res = parser::eval("  advance cursor 1337 ; ", parser::advance_cursor);
    assert(res.valid);
    assert(res.value == 1337);
    //debug_selector(res.value.selector.get());
  }
  {
    auto res = parser::eval("  update cursor 1337 set a='1', b=\"foo\"; ", parser::update_cursor);
    assert(res.valid);
    assert(res.value.cursor_id == 1337);
    assert((res.value.columns == vector<string>{"a", "b"}));
    assert((res.value.values == vector<string>{"1", "foo"}));
    //debug_selector(res.value.selector.get());
  }
}
#endif

string quote_string(const string& str) {
  stringstream res;
  res << '"';
  size_t left = 1024;
  for (char c : str) {
    if (left-- == 0) {
      res << "...";
      break;
    }
    int cc = (int)(unsigned char)c;
    if (cc >= 32 && cc <= 126 && cc != '\\' && cc != '"')
      res << c;
    else if (cc == '\\')
      res << "\\\\";
    else if (cc == '"')
      res << "\\\"";
    else
      res << "\\x" << hex << setfill('0') << setw(2) << cc;
  }
  res << '"';
  return res.str();
}

void error(string msg) {
  cout << "error " << quote_string(msg) << ";\n" << flush;
}

int main() {
#if TESTS
  parser_tests();
  return 0;
#endif

  SqlDb db;
  map<int, std::unique_ptr<SqlCursor>> cursors;
  int next_cursor_id = 0;

  string query;

  while (getline(cin, query)) {
    {
      auto res = parser::eval(query, parser::sql_select);
      if (res.valid) {
        int id = next_cursor_id++;
        auto cursor = db.select(res.value);
        if (!cursor) {
          error("Invalid column name");
          continue;
        }
        cursors[id] = std::move(cursor);
        cout << "ok " << id << ";\n" << flush;
        continue;
      }
    }
    {
      auto res = parser::eval(query, parser::get_cursor);
      if (res.valid) {
        auto it = cursors.find(res.value);
        if (it == cursors.end()) {
          error("invalid cursor ID");
          continue;
        }
        auto* cursor = it->second.get();
        if (cursor->valid()) {
          cout << "ok ";
          bool fst=1;
          for (size_t i = 0; i < cursor->table()->columns(); ++i) {
            if (!fst) cout << " ";
            auto& row = *cursor->value();
            cout << quote_string(row[i]);
            fst=0;
          }
          cout << ";\n" << flush;
        } else {
          cout << "done;\n" << flush;
        }
        continue;
      }
    }
    {
      auto res = parser::eval(query, parser::advance_cursor);
      if (res.valid) {
        auto it = cursors.find(res.value);
        if (it == cursors.end()) {
          error("invalid cursor ID");
          continue;
        }
        auto* cursor = it->second.get();
        if (!cursor->valid()) {
          error("invalid cursor");
          continue;
        }
        cursor->next();
        cout << "ok;\n" << flush;
        continue;
      }
    }
    {
      auto res = parser::eval(query, parser::sql_insert);
      if (res.valid) {
        if (!db.insert(res.value)) {
          error("Invalid table or column name");
          continue;
        }
        cout << "ok " << quote_string("insert into " + res.value.table_name + " completed successfully") << ";\n" << flush;
        continue;
      }
    }
    {
      auto res = parser::eval(query, parser::sql_create_table);
      if (res.valid) {
        if (!db.create_table(res.value)) {
          error("table already exists");
          continue;
        }

        cout << "ok " << quote_string("table " + res.value.table_name + " created successfully") << ";\n" << flush;
        continue;
      }
    }
    {
      auto res = parser::eval(query, parser::update_cursor);
      if (res.valid) {
        auto it = cursors.find(res.value.cursor_id);
        if (it == cursors.end()) {
          error("invalid cursor ID");
          continue;
        }
        auto* cursor = it->second.get();
        if (!cursor->valid()) {
          error("Invalid cursor");
          continue;
        }
        if (!cursor->update(res.value)) {
          error("Invalid column name");
          continue;
        }
        cout << "ok;\n" << flush;
        continue;
      }
    }
    error("syntax error");
  }
}
