// chess_trainer/static/ui/src/OpeningsTree.jsx
import React, { useState, useEffect, Fragment } from "react";

function TreeNode({ node, path, selectedOpenings, expandedPaths, onToggle }) {
  const [kids, setKids] = useState([]);
  const [manualOpen, setManualOpen] = useState();

  // Should this node auto‑open because of a search “deep‑navigate”?
  const autoOpen = expandedPaths.some(
    ep => ep.length === path.length && ep.every((m,i) => m === path[i])
  );
  useEffect(() => {
    if (autoOpen && manualOpen === false) {
      setManualOpen(undefined);
    }
  }, [autoOpen]);

  const isOpen = manualOpen !== undefined ? manualOpen : autoOpen;

  // Fetch children when opening
  useEffect(() => {
    if (!isOpen) return;
    fetch(
      `/api/openings?` + path.map(p => `path[]=${p}`).join("&")
    )
      .then(r => r.json())
      .then(d => setKids(d.children));
  }, [isOpen, path]);

  // Is this exact node selected?
  const isChecked = selectedOpenings.some(
    o => o.path.length === path.length && o.path.every((m,i) => m === path[i])
  );

  const uci         = path[path.length - 1] || "root";
  const openingName = node.opening_name;

  return (
    <li>
      <span
        style={{ cursor: "pointer", paddingRight: 4 }}
        onClick={() => setManualOpen(!isOpen)}
      >
        {isOpen ? "▼" : "▶"}
      </span>

      <label style={{ cursor: openingName ? "pointer" : "default", marginRight: 8 }}>
        <input
          type="checkbox"
          disabled={!openingName}
          checked={isChecked}
          onChange={() => onToggle({ path, name: openingName })}
          style={{ marginRight: 6 }}
        />
        {uci}
        {openingName && <small> ({openingName})</small>}
      </label>

      {isOpen && (
        <ul style={{ paddingLeft: 20, listStyle: "none" }}>
          {kids.map(child => (
            <TreeNode
              key={child.uci}
              node={child}
              path={[...path, child.uci]}
              selectedOpenings={selectedOpenings}
              expandedPaths={expandedPaths}
              onToggle={onToggle}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function OpeningsTree() {
  const [roots, setRoots] = useState([]);
  const [selectedOpenings, setSelectedOpenings] = useState([]);
  const [expandedPaths, setExpandedPaths] = useState([]);
  const [search, setSearch]   = useState("");
  const [results, setResults] = useState([]);

  // Load first‑move roots
  useEffect(() => {
    fetch(`/api/openings`)
      .then(r => r.json())
      .then(d => setRoots(d.children));
  }, []);

  // Debounced search
  useEffect(() => {
    if (!search) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      fetch(`/api/openings/search?q=${encodeURIComponent(search)}`)
        .then(r => r.json())
        .then(d => setResults(d.matches));
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  // Toggle a named opening on/off
  const onToggle = ({ path, name }) => {
    setSelectedOpenings(prev => {
      const exists = prev.find(
        o => o.path.length === path.length && o.path.every((m,i) => m === path[i])
      );
      if (exists) {
        return prev.filter(o => o !== exists);
      } else {
        return [...prev, { path, name }];
      }
    });
  };

  return (
    <section style={{ marginBottom: "2rem" }}>
      <h2>Select openings</h2>

      <input
        placeholder="Search…"
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{ width: "100%", marginBottom: "0.5rem" }}
      />

      {search && (
        <ul
          style={{
            border: "1px solid #444",
            padding: "0.5rem",
            listStyle: "none",
            maxHeight: "200px",
            overflowY: "auto",
          }}
        >
          {results.map(r => {
            const isSel = selectedOpenings.some(
              o => o.path.length === r.path.length && o.path.every((m,i) => m === r.path[i])
            );
            return (
              <li
                key={r.path.join("-")}
                style={{
                  cursor: "pointer",
                  background: isSel ? "#333" : "transparent",
                  color: isSel ? "#fff" : "#ddd",
                  padding: "4px 8px",
                }}
                onClick={() => {
                  onToggle({ path: r.path, name: r.opening_name });
                  const prefixes = r.path.map((_, i) => r.path.slice(0, i + 1));
                  setExpandedPaths(prefixes);
                }}
              >
                {isSel ? "☑️" : "⬜"} {r.opening_name} ({r.path.join(" ")})
              </li>
            );
          })}
        </ul>
      )}

      <ul style={{ listStyle: "none", paddingLeft: 0 }}>
        {roots.map(c => (
          <TreeNode
            key={c.uci}
            node={c}
            path={[c.uci]}
            selectedOpenings={selectedOpenings}
            expandedPaths={expandedPaths}
            onToggle={onToggle}
          />
        ))}
      </ul>

      {/* Hidden inputs so Flask sees opening names */}
      {selectedOpenings.map((o, i) => (
        <Fragment key={i}>
          <input type="hidden" name="white" value={o.name} />
          <input type="hidden" name="black" value={o.name} />
        </Fragment>
      ))}
    </section>
  );
}
