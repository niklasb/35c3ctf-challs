#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <string>
#include <vector>
#include <iostream>

namespace pwndb {

constexpr int INLINE_KEY_SIZE = 128;
using FixedString = std::array<char, INLINE_KEY_SIZE>;

template <typename T>
struct SSTableItem {
  std::string key;
  T value;
  SSTableItem(std::string key, T value)
    : key(std::move(key)), value(std::move(value)) {}

  bool operator<(const std::string& other) const {
    return key < other;
  }

  bool operator>(const std::string& other) const {
    return key > other;
  }

  bool operator<(const SSTableItem& other) const {
    return key < other.key;
  }

  bool operator==(const SSTableItem& other) const {
    return key == other.key;
  }
};

template <typename T>
struct SSTableCursor {
  using Iter = typename std::vector<SSTableItem<T>>::const_iterator;

  SSTableCursor(Iter start, Iter end)
    : m_start(start), m_end(end)
  {}

  bool valid() const { return m_start < m_end; }
  void next() {
    m_start++;
  }

  const SSTableItem<T>* item() const {
    return &*m_start;
  }

private:
  Iter m_start, m_end;
};

struct Border {
  const std::string bound;
  bool inclusive;
  Border(std::string bound, bool inclusive)
    : bound(std::move(bound)), inclusive(inclusive) {}
};

template <typename T>
struct SSTable {
  std::vector<SSTableItem<T>> entries;

  void debug() const {
    using namespace std;
    cerr << "Entries (" << entries.size() << "):" << endl;
    for (auto& entry : entries) {
      cerr <<  "  " << entry.key << " -> " << entry.value << endl;
    }
  }

  void insert(SSTableItem<T> item) {
    entries.push_back(std::move(item));
    for (int i = (int)entries.size() - 2; i >= 0; --i) {
      if (entries[i + 1] < entries[i])
        std::swap(entries[i], entries[i + 1]);
      else
        break;
    }
  }

  const SSTableItem<T>& get(uint64_t idx) const {
    return entries[idx];
  }

  SSTableCursor<T> find(Border lo, Border hi) const {
    auto lb = [&](const std::string& bound) {
      return std::lower_bound(entries.begin(), entries.end(), bound);
    };
    auto ub = [&](const std::string& bound) {
      return std::upper_bound(entries.begin(), entries.end(), bound,
                    [&](const std::string& bound, const SSTableItem<T>& item) {
                      return item > bound;
                    });
    };

    auto l = lo.inclusive ? lb(lo.bound) : ub(lo.bound);
    auto r = hi.inclusive ? ub(hi.bound) : lb(hi.bound);
    return SSTableCursor<T>(l, max(l, r));
  }
};

}
