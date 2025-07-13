import React, { useState, useEffect } from "react";

function TreeNode({ side, path, onSelect }) {
  const [children, setChildren] = useState([]);
  const [open, setOpen]       = useState(false);

  useEffect(() => {
    if (open) {
      fetch(`/api/openings?side=${side}&` + path.map(p=>`path[]=${p}`).join("&"))
        .then(r => r.json())
        .then(data => setChildren(data.children));
    }
  }, [open, path, side]);

  return (
    <li>
      <span onClick={()=>setOpen(o=>!o)} style={{ cursor: "pointer" }}>
        {open ? "▼" : "▶"}
      </span>
      <input
        type="checkbox"
        name={side}
        value={path[path.length-1] || ""}
        onChange={e => onSelect(path)}
      />
      <small style={{ marginLeft: 4 }}>
        {children.find(c=>c.uci===path[path.length-1])?.opening_name}
      </small>
      {open && (
        <ul style={{ paddingLeft: 16 }}>
          {children.map(c => (
            <TreeNode
              key={c.uci}
              side={side}
              path={[...path, c.uci]}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function OpeningsTree({ side }) {
  const [roots, setRoots] = useState([]);
  const [selectedPaths, setSelected] = useState([]);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);

  // load first-move roots
  useEffect(() => {
    fetch(`/api/openings?side=${side}`)
      .then(r => r.json())
      .then(d => setRoots(d.children));
  }, [side]);

  // search handler
  useEffect(() => {
    if (!search) return setResults([]);
    const t = setTimeout(() => {
      fetch(`/api/openings/search?q=${encodeURIComponent(search)}`)
        .then(r => r.json())
        .then(d => setResults(d.matches));
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const handleSelect = path => {
    setSelected(sel =>
      sel.some(p => JSON.stringify(p)===JSON.stringify(path))
        ? sel.filter(p=>JSON.stringify(p)!==JSON.stringify(path))
        : [...sel, path]
    );
  };

  const goTo = path => {
    // clear and then expand that path (you’ll need some refs or state to auto-open)
    handleSelect(path);
    // TODO: trigger UI scroll/expand to this node
  };

  return (
    <section>
      <h2>{side[0].toUpperCase()+side.slice(1)} openings</h2>
      <input
        placeholder="Search openings…"
        value={search}
        onChange={e => setSearch(e.target.value)}
      />
      {search && (
        <ul className="search-results">
          {results.map(r => (
            <li key={r.path.join("-")} onClick={()=>goTo(r.path)}>
              {r.opening_name} ({r.path.join(" ")}…)
            </li>
          ))}
        </ul>
      )}
      <ul className="tree-root">
        {roots.map(c => (
          <TreeNode
            key={c.uci}
            side={side}
            path={[c.uci]}
            onSelect={handleSelect}
          />
        ))}
      </ul>
      {/* hidden inputs so form submits selected paths */}
      {selectedPaths.map((path,i) => (
        <input
          key={i}
          type="hidden"
          name={side}
          value={path.join(" ")}
        />
      ))}
    </section>
  );
}
