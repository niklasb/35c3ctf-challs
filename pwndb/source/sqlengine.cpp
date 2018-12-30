#include <algorithm>
#include <array>
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include <unordered_set>
#include <cassert>
#include <iostream>

#include "sqlengine.h"

namespace pwndb {

using SqlRecord = std::vector<std::string>;
using RowSet = std::unordered_set<uint64_t>;

const SqlRecord* SqlCursor::value() const {
  return &m_tbl->get(row_index());
}

bool SqlCursor::update(const SqlUpdate& doit) {
  return m_tbl->update(row_index(), doit);
}

std::unique_ptr<SqlCursor> SqlTable::select(const SqlSelector* selector) {
  using namespace std;
  switch (selector->type()) {
    case SqlSelectorType::ALL: {
      return std::make_unique<AllCursor>(this);
    }
    case SqlSelectorType::TERM: {
      const auto* sel = dynamic_cast<const SqlSelectorTerm*>(selector);
      size_t col_idx;
      if (!find_column(sel->column, &col_idx))
        return nullptr;
      return std::make_unique<IndexCursor>(this,
            m_indexes[col_idx].find(sel->lo, sel->hi));
    }
    case SqlSelectorType::AND: {
      const auto* sel = dynamic_cast<const SqlSelectorAnd*>(selector);
      RowSet a, res;
      {
        auto cursor1 = select(sel->a.get());
        if (!cursor1)
          return nullptr;
        while (cursor1->valid()) {
          a.insert(cursor1->row_index());
          cursor1->next();
        }
      }
      auto cursor2 = select(sel->b.get());
      if (!cursor2)
        return nullptr;
      while (cursor2->valid()) {
        uint64_t idx = cursor2->row_index();
        if (a.count(idx))
          res.insert(idx);
        cursor2->next();
      }
      return std::make_unique<CustomCursor<RowSet>>(this, res);
    }
    case SqlSelectorType::OR: {
      const auto* sel = dynamic_cast<const SqlSelectorOr*>(selector);
      RowSet res;
      {
        auto cursor1 = select(sel->a.get());
        if (!cursor1)
          return nullptr;
        while (cursor1->valid()) {
          res.insert(cursor1->row_index());
          cursor1->next();
        }
      }
      auto cursor2 = select(sel->b.get());
      if (!cursor2)
        return nullptr;
      while (cursor2->valid()) {
        res.insert(cursor2->row_index());
        cursor2->next();
      }
      return std::make_unique<CustomCursor<RowSet>>(this, res);
    }
  }
  assert(0);
  return nullptr;
}

}
