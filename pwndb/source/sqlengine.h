#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include <cassert>
#include <iostream>

#include "sstable.h"

namespace pwndb {

struct SqlInsert {
  std::string table_name;
  std::vector<std::string> columns;
  std::vector<std::vector<std::string>> values;
};

struct SqlUpdate {
  int cursor_id;
  std::vector<std::string> columns, values;
};

struct SqlCreateTable {
  std::string table_name;
  std::vector<std::string> columns;
};

using SqlRecord = std::vector<std::string>;
struct SqlTable;

struct SqlCursor {
  SqlCursor(SqlTable* tbl) : m_tbl(tbl) {}
  virtual ~SqlCursor() {}
  virtual bool valid() const = 0;
  virtual void next() = 0;
  virtual uint64_t row_index() const = 0;
  const SqlTable* table() const {
    return m_tbl;
  }

  const SqlRecord* value() const;
  bool update(const SqlUpdate& update);

private:
  SqlTable* m_tbl;
};

enum class SqlSelectorType {
  OR, AND, TERM, ALL,
};

struct SqlSelector {
  virtual ~SqlSelector() {}
  virtual SqlSelectorType type() const = 0;
};

struct SqlSelectorAll : public SqlSelector {
  virtual SqlSelectorType type() const override {
    return SqlSelectorType::ALL;
  }
};

struct SqlSelectorTerm : public SqlSelector {
  std::string column;
  Border lo, hi;
  SqlSelectorTerm(std::string column, Border lo, Border hi)
    : column(column), lo(lo), hi(hi) {}
  virtual SqlSelectorType type() const override {
    return SqlSelectorType::TERM;
  }
};

struct SqlSelectorAnd : public SqlSelector {
  std::unique_ptr<SqlSelector> a, b;
  SqlSelectorAnd(std::unique_ptr<SqlSelector> a, std::unique_ptr<SqlSelector> b)
    : a(std::move(a)), b(std::move(b)) {}
  virtual SqlSelectorType type() const override {
    return SqlSelectorType::AND;
  }
};

struct SqlSelectorOr : public SqlSelector {
  std::unique_ptr<SqlSelector> a, b;
  SqlSelectorOr(std::unique_ptr<SqlSelector> a, std::unique_ptr<SqlSelector> b)
    : a(std::move(a)), b(std::move(b)) {}
  virtual SqlSelectorType type() const override {
    return SqlSelectorType::OR;
  }
};

struct SqlSelect {
  std::string table_name;
  std::unique_ptr<SqlSelector> selector;
};

using SqlIndex = SSTable<uint64_t>;

struct SqlTable {
  SqlTable(std::vector<std::string> field_names)
    : m_field_names(field_names)
  {
    for (auto& field : field_names) {
      std::transform(field.begin(), field.end(), field.begin(), ::tolower);
      m_indexes.push_back(SqlIndex());
    }
  }

  size_t columns() const { return m_field_names.size(); }

  bool find_column(std::string name, size_t* res) const {
    std::transform(name.begin(), name.end(), name.begin(), ::tolower);
    for (size_t i = 0; i < m_field_names.size(); ++i)
      if (m_field_names[i] == name) {
        *res = i;
        return true;
      }
    return false;
  }

  void insert(SqlRecord record) {
    using namespace std;
    uint64_t idx = m_records.size();
    m_records.push_back(std::move(record));
    const auto& row = m_records.back();

    for (size_t i = 0; i < columns(); ++i) {
      m_indexes[i].insert(SSTableItem<uint64_t>(row[i], idx));
    }
  }

  bool insert(const SqlInsert& doit) {
    for (const auto& row : doit.values) {
      if (row.size() < doit.columns.size())
        return false;  // let's not?
      SqlRecord record(m_field_names.size());
      for (size_t i = 0; i < doit.columns.size(); ++i) {
        size_t column;
        if (!find_column(doit.columns[i], &column))
          return false;
        record[column] = row[i];
      }
      insert(std::move(record));
    }
    return true;
  }

  bool update(size_t row_index, const SqlUpdate& doit) {
    auto& record = m_records[row_index];
    for (size_t i = 0; i < doit.columns.size(); ++i) {
      size_t column;
      if (!find_column(doit.columns[i], &column))
        return false;
      record[column] = doit.values[i];
    }
    return true;
  }

  const SqlRecord& get(uint64_t idx) const {
    return m_records[idx];
  }

  const uint64_t size() const {
    return m_records.size();
  }

  std::unique_ptr<SqlCursor> select(const SqlSelector* selector);

  std::vector<std::string> m_field_names;
  std::vector<SqlRecord> m_records;
  std::vector<SqlIndex> m_indexes;
};

struct AllCursor : public SqlCursor {
  AllCursor(SqlTable* tbl) :
    SqlCursor(tbl), m_cur(0), m_end(tbl->size()) {}

  virtual bool valid() const override {
    return m_cur < m_end;
  }
  virtual void next() override {
    m_cur++;
  }
  virtual uint64_t row_index() const override {
    return m_cur;
  }

  uint64_t m_cur, m_end;
};

struct IndexCursor : public SqlCursor {
  IndexCursor(SqlTable* tbl, SSTableCursor<uint64_t> cursor) :
    SqlCursor(tbl), m_cursor(std::move(cursor)) {}

  virtual bool valid() const override {
    return m_cursor.valid();
  }
  virtual void next() override {
    m_cursor.next();
  }

  virtual uint64_t row_index() const override {
    return m_cursor.item()->value;
  }

private:
  SSTableCursor<uint64_t> m_cursor;
};

template <typename C>
struct CustomCursor : public SqlCursor {
  CustomCursor(SqlTable* tbl, C rows)
    : SqlCursor(tbl), m_rows(std::move(rows)), m_cur(m_rows.begin()), m_end(m_rows.end())
  {}

  virtual bool valid() const override {
    return m_cur != m_end;
  }

  virtual void next() override {
    m_cur++;
  }

  virtual uint64_t row_index() const override {
    return *m_cur;
  }

private:
  C m_rows;
  typename C::const_iterator m_cur, m_end;
};

struct SqlDb {
  std::unique_ptr<SqlCursor> select(const SqlSelect& select) const {
    auto it = m_tables.find(select.table_name);
    if (it == m_tables.end())
      return nullptr;
    return it->second->select(select.selector.get());
  }

  bool insert(const SqlInsert& doit) {
    auto it = m_tables.find(doit.table_name);
    if (it == m_tables.end())
      return false;
    return it->second->insert(doit);
  }

  SqlTable* create_table(const SqlCreateTable& doit) {
    if (m_tables.count(doit.table_name))
      return nullptr;
    auto tab = std::make_unique<SqlTable>(doit.columns);
    auto* res = tab.get();
    m_tables[doit.table_name] = std::move(tab);
    return res;
  }


  std::map<std::string, std::unique_ptr<SqlTable>> m_tables;
};

}
