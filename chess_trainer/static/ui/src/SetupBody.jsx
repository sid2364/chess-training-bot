// chess_trainer/static/ui/src/SetupBody.jsx
// The whole interactive setup body: openings tree (lazy-loaded from /api/openings),
// search, selected lines, board preview of the hovered/last-selected line,
// bot strength slider and opponent fields. Rendered into #react-root inside the
// Flask form, so every input name matches what chess_trainer/ui.py reads.
import React, { useState, useEffect, useMemo, useCallback } from "react";

const START = [
  "r","n","b","q","k","b","n","r",
  "p","p","p","p","p","p","p","p",
  "","","","","","","","",
  "","","","","","","","",
  "","","","","","","","",
  "","","","","","","","",
  "P","P","P","P","P","P","P","P",
  "R","N","B","Q","K","B","N","R",
];
const GLYPH = { p: "\u265F", n: "\u265E", b: "\u265D", r: "\u265C", q: "\u265B", k: "\u265A" };
const sqIndex = (sq) => (8 - parseInt(sq[1], 10)) * 8 + (sq.charCodeAt(0) - 97);
const samePath = (a, b) => a.length === b.length && a.every((m, i) => m === b[i]);

// Replay a list of UCI moves. Enough for opening-book lines: no castling,
// no en passant, promotions fall back to the moved piece.
function play(path) {
  const board = START.slice();
  const sans = [];
  let last = null;
  for (const uci of path) {
    if (!uci || uci.length < 4) continue;
    const from = sqIndex(uci.slice(0, 2));
    const to = sqIndex(uci.slice(2, 4));
    const piece = board[from];
    if (!piece) continue;
    const capture = board[to] !== "";
    const letter = piece.toLowerCase() === "p" ? "" : piece.toUpperCase();
    sans.push(
      letter === ""
        ? (capture ? uci[0] + "x" + uci.slice(2, 4) : uci.slice(2, 4))
        : letter + (capture ? "x" : "") + uci.slice(2, 4)
    );
    board[to] = piece;
    board[from] = "";
    last = [from, to];
  }
  return { board, sans, last };
}

function numbered(sans) {
  return sans
    .map((san, i) => (i % 2 === 0 ? `${i / 2 + 1}. ${san}` : san))
    .join(" ");
}

function phrase(n) {
  if (n <= -200) return "A clear step below you \u2014 space to rehearse the moves.";
  if (n < 0) return "Slightly weaker than your opponent rating.";
  if (n === 0) return "Matched to your opponent rating.";
  if (n < 200) return "A little stronger \u2014 punishes loose play in the line.";
  return "Well above you \u2014 expect to be tested out of the book.";
}

function TreeNode({ info, path, depth, ctx }) {
  const [kids, setKids] = useState(null);
  const [manualOpen, setManualOpen] = useState(undefined);

  const autoOpen = ctx.expandedPaths.some((ep) => samePath(ep, path));
  useEffect(() => {
    if (autoOpen && manualOpen === false) setManualOpen(undefined);
  }, [autoOpen]);

  const isOpen = manualOpen !== undefined ? manualOpen : autoOpen;

  useEffect(() => {
    if (!isOpen || kids !== null) return;
    const query = path.map((p) => `path[]=${encodeURIComponent(p)}`).join("&");
    fetch(`/api/openings?${query}`)
      .then((r) => r.json())
      .then((d) => setKids(d.children || []))
      .catch(() => setKids([]));
  }, [isOpen, kids, path]);

  const name = info.opening_name;
  const isChecked = ctx.selected.some((o) => samePath(o.path, path));
  const isHovered = samePath(ctx.hover, path);
  const san = useMemo(() => {
    const { sans } = play(path);
    return sans[sans.length - 1] || path[path.length - 1];
  }, [path]);

  const rowClass = [
    "tree-row",
    isChecked ? "is-checked" : "",
    isHovered ? "is-hovered" : "",
  ].filter(Boolean).join(" ");

  return (
    <div>
      <div
        className={rowClass}
        style={{ paddingLeft: depth * 18 + 5.6 }}
        onMouseEnter={() => ctx.onHover(path)}
      >
        <span className="tree-caret" onClick={() => setManualOpen(!isOpen)}>
          {isOpen ? "\u25BC" : "\u25B6"}
        </span>
        <label className={name ? "tree-label" : "tree-label is-plain"}>
          <input
            type="checkbox"
            disabled={!name}
            checked={isChecked}
            onChange={() => ctx.onToggle({ path, name })}
          />
          <span className="tree-move">{ctx.showUci ? path[path.length - 1] : san}</span>
          {name && <span className="tree-name">{name}</span>}
        </label>
      </div>

      {isOpen && kids !== null && kids.length === 0 && (
        <div className="tree-empty" style={{ paddingLeft: (depth + 1) * 18 + 5.6 }}>
          no continuations in the book
        </div>
      )}
      {isOpen && kids && kids.map((child) => (
        <TreeNode
          key={child.uci}
          info={child}
          path={[...path, child.uci]}
          depth={depth + 1}
          ctx={ctx}
        />
      ))}
    </div>
  );
}

export default function SetupBody({ initial }) {
  const [roots, setRoots] = useState([]);
  const [selected, setSelected] = useState([]);
  const [expandedPaths, setExpandedPaths] = useState([]);
  const [hover, setHover] = useState([]);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const [offset, setOffset] = useState(initial.challenge ?? 0);
  const [username, setUsername] = useState(initial.username ?? "");
  const [allowAll, setAllowAll] = useState(!!initial.allowAll);
  const [color, setColor] = useState(initial.color ?? "random");
  const showUci = false;

  useEffect(() => {
    fetch("/api/openings")
      .then((r) => r.json())
      .then((d) => setRoots(d.children || []))
      .catch(() => setRoots([]));
  }, []);

  useEffect(() => {
    if (!search) { setResults([]); return; }
    const t = setTimeout(() => {
      fetch(`/api/openings/search?q=${encodeURIComponent(search)}`)
        .then((r) => r.json())
        .then((d) => setResults(d.matches || []))
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const onToggle = useCallback(({ path, name }) => {
    if (!name) return;
    setSelected((prev) => {
      const existing = prev.find((o) => samePath(o.path, path));
      return existing ? prev.filter((o) => o !== existing) : [...prev, { path, name }];
    });
    setHover(path);
  }, []);

  const ctx = { selected, expandedPaths, hover, onToggle, onHover: setHover, showUci };

  const view = useMemo(() => play(hover), [hover]);
  const hoverName = useMemo(() => {
    const inSelected = selected.find((o) => samePath(o.path, hover));
    if (inSelected) return inSelected.name;
    const inResults = results.find((r) => samePath(r.path, hover));
    return inResults ? inResults.opening_name : null;
  }, [hover, selected, results]);

  return (
    <div className="columns">
      <div className="col">

        <section className="panel">
          <div className="panel-head">
            <h2 className="panel-title">Repertoire</h2>
            <span className="panel-note">
              {selected.length === 0
                ? "no lines picked"
                : `${selected.length} ${selected.length === 1 ? "line" : "lines"} picked`}
            </span>
          </div>

          <input
            className="input"
            placeholder="Search openings: Sicilian, Vienna, Queen's Gambit"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          {search && (
            <ul className="results">
              {results.map((r) => {
                const isSel = selected.some((o) => samePath(o.path, r.path));
                return (
                  <li
                    key={r.path.join("-")}
                    className={isSel ? "result is-selected" : "result"}
                    onMouseEnter={() => setHover(r.path)}
                    onClick={() => {
                      onToggle({ path: r.path, name: r.opening_name });
                      setExpandedPaths(r.path.map((_, i) => r.path.slice(0, i + 1)));
                    }}
                  >
                    <span className="result-mark" />
                    <span className="result-name">{r.opening_name}</span>
                    <span className="result-moves">{numbered(play(r.path).sans)}</span>
                  </li>
                );
              })}
              {results.length === 0 && (
                <li className="tree-empty">No lines in the book match that.</li>
              )}
            </ul>
          )}

          <div className="tree">
            {roots.map((c) => (
              <TreeNode key={c.uci} info={c} path={[c.uci]} depth={0} ctx={ctx} />
            ))}
          </div>
        </section>

        <section className="panel">
          <h2 className="panel-title" style={{ marginBottom: 11.2 }}>Selected lines</h2>
          {selected.length > 0 ? (
            <div className="chips">
              {selected.map((o) => (
                <span
                  key={o.path.join("-")}
                  className="chip"
                  onMouseEnter={() => setHover(o.path)}
                >
                  <span className="chip-name">{o.name}</span>
                  <span className="chip-moves">{numbered(play(o.path).sans)}</span>
                  <span className="chip-x" onClick={() => onToggle(o)}>&times;</span>
                </span>
              ))}
            </div>
          ) : (
            <p className="empty-note">
              Nothing picked yet. With no preference the bot plays the first three defaults
              for each side &mdash; tick lines above to force the games into them.
            </p>
          )}

          {/* Hidden inputs so Flask sees the chosen opening names */}
          {selected.map((o, i) => (
            <React.Fragment key={i}>
              <input type="hidden" name="white" value={o.name} />
              <input type="hidden" name="black" value={o.name} />
            </React.Fragment>
          ))}
        </section>

        <section className="panel">
          <h2 className="panel-title" style={{ marginBottom: 11.2 }}>Opponent</h2>
          <div className="opponent-grid">
            <div>
              <div className="field">
                <label htmlFor="username">Your Lichess username</label>
                <input
                  className="input"
                  id="username"
                  type="text"
                  name="username"
                  placeholder="for e.g., DrNykterstein"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
              <label className="checkline">
                <input
                  id="allow_all"
                  type="checkbox"
                  name="allow_all"
                  value="1"
                  checked={allowAll}
                  onChange={(e) => setAllowAll(e.target.checked)}
                />
                Allow other usernames to challenge (free for all)
              </label>
            </div>
            <div>
              <div className="sub-label">You play as</div>
              <div className="sides">
                {[
                  ["random", "Random"],
                  ["white", "White"],
                  ["black", "Black"],
                ].map(([value, label]) => (
                  <label
                    key={value}
                    className={color === value ? "side-opt is-on" : "side-opt"}
                  >
                    <input
                      type="radio"
                      name="color"
                      value={value}
                      checked={color === value}
                      onChange={() => setColor(value)}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </section>

      </div>

      <div className="col col-side">

        <section className="panel">
          <div className="panel-head">
            <h2 className="panel-title">Line preview</h2>
            <span className="panel-note">
              {hover.length % 2 === 0 ? "White to move" : "Black to move"}
            </span>
          </div>

          <div className="board">
            {view.board.map((piece, i) => {
              const light = ((i >> 3) + (i % 8)) % 2 === 0;
              const hit = view.last && (i === view.last[0] || i === view.last[1]);
              const cls = ["square", light ? "light" : "dark", hit ? "hit" : ""]
                .filter(Boolean).join(" ");
              return (
                <div key={i} className={cls}>
                  {piece && (
                    <span className={piece === piece.toUpperCase() ? "piece-w" : "piece-b"}>
                      {GLYPH[piece.toLowerCase()]}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          <div className="line-name">
            {hoverName || (hover.length
              ? `Position after ${hover.length} moves`
              : "Starting position")}
          </div>
          <div className="line-moves">
            {numbered(view.sans) || "Hover a line to see it on the board."}
          </div>
        </section>

        <section className="panel">
          <h2 className="panel-title" style={{ marginBottom: 11.2 }}>Bot strength</h2>
          <div className="strength-value">
            <span className="strength-number">
              {(offset > 0 ? "+" : offset < 0 ? "\u2212" : "\u00B1") + Math.abs(offset)}
            </span>
            <span className="strength-unit">Elo, relative to your opponent rating</span>
          </div>
          <input
            className="strength-slider"
            type="range"
            min="-300"
            max="300"
            step="25"
            value={offset}
            onChange={(e) => setOffset(parseInt(e.target.value, 10))}
          />
          <div className="strength-scale">
            <span>&minus;300</span><span>even</span><span>+300</span>
          </div>
          <div className="strength-phrase">{phrase(offset)}</div>
          <input type="hidden" name="challenge" value={offset} />
        </section>

      </div>
    </div>
  );
}
