// Glass Box web UI: board, buttons, explanation, stats, questions.   OWNER: Srikar
// Talks to web/app.py over one WebSocket (protocol is documented at the top of app.py).
// Columns are 0-6 in messages and 1-7 on screen. Board rows: row 0 = bottom.
"use strict";

const ROWS = 6, COLS = 7;
const $ = (id) => document.getElementById(id);

let ws = null;
let state = null;          // last "state" message
let turn = null;           // last agent turn (explanation + trace)
let turnAtLen = -1;        // history length right after that agent move
let thinking = false;
let prevBoard = null;
let hoverCol = null;

// ------------------------------------------------------------------ build DOM
const cells = [];          // cells[r][c] -> .disc element, r = 0 is the bottom row
function buildBoard() {
  const board = $("board"), drop = $("drop"), scores = $("scores");
  for (let r = 0; r < ROWS; r++) cells.push([]);
  for (let i = 0; i < ROWS; i++) {           // DOM order: top row first
    const r = ROWS - 1 - i;
    for (let c = 0; c < COLS; c++) {
      const cell = document.createElement("div");
      cell.className = "cell";
      cell.dataset.col = c;
      const disc = document.createElement("div");
      disc.className = "disc";
      cell.appendChild(disc);
      cells[r][c] = disc;
      cell.addEventListener("click", () => play(c));
      cell.addEventListener("mouseenter", () => setHover(c));
      cell.addEventListener("mouseleave", () => setHover(null));
      board.appendChild(cell);
    }
  }
  for (let c = 0; c < COLS; c++) {
    const g = document.createElement("div");
    g.className = "ghost";
    drop.appendChild(g);
    scores.appendChild(document.createElement("span"));
  }
}

// ------------------------------------------------------------------ websocket
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => setConn("connected", "ok");
  ws.onclose = () => {
    setConn("disconnected — retrying…", "bad");
    thinking = false;
    state = null;
    render();
    setTimeout(connect, 2000);
  };
  ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  else toast("Not connected to the server.");
}

function onMessage(msg) {
  switch (msg.type) {
    case "hello":
      fillEngines(msg.engines, msg.default_engine);
      $("status").textContent = "Press “New game” to start.";
      break;
    case "thinking":
      thinking = true;
      render();
      break;
    case "state":
      thinking = false;
      if (msg.agent_turn) {
        turn = msg.agent_turn;
        turnAtLen = msg.history.length;
      } else if (!state || msg.history.length < state.history.length || msg.history.length === 0) {
        turn = null;                       // new game or undo: old explanation no longer applies
        turnAtLen = -1;
      }
      state = msg;
      render();
      break;
    case "answer":
      addLog(msg.question, msg.text);
      break;
    case "error":
      thinking = false;
      toast(msg.text);
      render();
      break;
  }
}

// ------------------------------------------------------------------ actions
function play(col) {
  if (!state || thinking || !state.human_to_move || !state.legal.includes(col)) return;
  send({ type: "move", col });
}

function newGame() {
  $("log").innerHTML = "";
  prevBoard = null;
  send({
    type: "new_game",
    engine: $("engine").value,
    human_first: $("first").value === "1",
    time_limit: parseFloat($("time").value),
  });
}

function ask(question) {
  question = question.trim();
  if (!question) return;
  send({ type: "ask", question });
}

// ------------------------------------------------------------------ rendering
function render() {
  renderBoard();
  renderStatus();
  renderScores();
  renderExplanation();
  renderStats();
  $("undo").disabled = !state || thinking || state.history.length === 0;
  $("board").classList.toggle("locked", !state || thinking || !state.human_to_move);
}

function humanSymbol() { return state && state.human_player === 0 ? "x" : "o"; }

function renderBoard() {
  const board = state ? state.board : null;
  const win = new Set((state?.winning_cells || []).map(([r, c]) => `${r},${c}`));
  const fresh = turn && state && state.history.length === turnAtLen;
  const showFacts = $("t-cells").checked && fresh;
  const factCells = new Map();               // "r,c" -> "fact" | "fact-target"
  if (showFacts) {
    for (const f of turn.explanation.facts) {
      f.cells.forEach(([r, c], i) => {
        const k = `${r},${c}`;
        if (i === 0 || !factCells.has(k)) factCells.set(k, i === 0 ? "fact-target" : "fact");
      });
    }
  }
  const pvCells = $("t-pv").checked && fresh ? expectedLineCells() : new Map();
  const last = lastMoveCell();

  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const d = cells[r][c];
      const v = board ? board[r][c] : 0;
      const k = `${r},${c}`;
      d.className = "disc" + (v === 1 ? " x" : v === -1 ? " o" : "");
      if (v !== 0 && prevBoard && prevBoard[r][c] === 0) d.classList.add("new");
      if (last && last[0] === r && last[1] === c) d.classList.add("last");
      if (win.has(k)) d.classList.add("win");
      if (factCells.has(k)) d.classList.add(factCells.get(k));
      d.innerHTML = pvCells.has(k) ? `<span class="pvnum">${pvCells.get(k)}</span>` : "";
    }
  }
  prevBoard = board ? board.map((row) => row.slice()) : null;
  setHover(hoverCol);
}

function lastMoveCell() {
  if (!state || state.history.length === 0) return null;
  const c = state.history[state.history.length - 1];
  for (let r = ROWS - 1; r >= 0; r--) if (state.board[r][c] !== 0) return [r, c];
  return null;
}

// Where the rest of the agent's expected line would land on the current board.
function expectedLineCells() {
  const out = new Map();
  const pv = turn.trace.moves.find((m) => m.col === turn.trace.chosen)?.pv || [];
  const height = [];
  for (let c = 0; c < COLS; c++) {
    let h = 0;
    while (h < ROWS && state.board[h][c] !== 0) h++;
    height.push(h);
  }
  pv.slice(1).forEach((c, i) => {
    if (height[c] < ROWS) out.set(`${height[c]++},${c}`, i + 1);
  });
  return out;
}

function renderStatus() {
  const el = $("status");
  el.classList.remove("thinking");
  if (!state) { el.textContent = ws && ws.readyState === 1 ? "Press “New game” to start." : "Connecting to the server…"; return; }
  const you = state.human_player === 0 ? "red" : "yellow";
  if (state.over) {
    el.textContent = state.result === "human" ? "You win! 🎉"
      : state.result === "agent" ? "The agent wins." : "Draw — the board is full.";
  } else if (thinking) {
    el.textContent = "Agent is thinking";
    el.classList.add("thinking");
  } else if (state.human_to_move) {
    el.textContent = `Your turn (you are ${you}) — click a column or press 1–7.`;
  } else {
    el.textContent = "Agent to move";
  }
}

function renderScores() {
  const spans = $("scores").children;
  const show = $("t-scores").checked && turn;
  for (let c = 0; c < COLS; c++) {
    const s = spans[c];
    s.className = "";
    s.textContent = "";
    if (!show) continue;
    const m = turn.trace.moves.find((m) => m.col === c);
    if (!m) { s.textContent = "—"; continue; }
    s.textContent = m.score_text;
    s.title = `Column ${c + 1}: ${m.score_text} (depth ${m.depth})`;
    if (c === turn.trace.chosen) s.className = "best";
    else if (m.score_text.startsWith("loss")) s.className = "lose";
  }
}

function renderExplanation() {
  const sent = $("sentence"), chips = $("concepts");
  chips.innerHTML = "";
  if (!turn) {
    sent.textContent = "The agent's explanation appears here after its move.";
    sent.classList.add("muted");
    return;
  }
  sent.classList.remove("muted");
  sent.textContent = turn.explanation.sentence;
  for (const c of turn.explanation.concepts) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = c;
    chips.appendChild(chip);
  }
}

function renderStats() {
  $("stats-card").classList.toggle("hidden", !$("t-stats").checked && !$("t-pv").checked);
  const dl = $("stats");
  dl.classList.toggle("hidden", !$("t-stats").checked);
  const pvEl = $("pv");
  if (!turn) {
    dl.innerHTML = "<dt>—</dt><dd>no search yet</dd>";
    pvEl.classList.add("hidden");
    return;
  }
  const t = turn.trace;
  const rows = [
    ["Evaluator", t.evaluator],
    ["Depth", `${t.depth} plies`],
    ["Nodes", t.nodes.toLocaleString()],
    ["Time", `${t.time_s.toFixed(2)} s`],
    ["Nodes / s", t.nps ? t.nps.toLocaleString() : "—"],
    ["Score", `${t.score_text}  (static ${t.static_score >= 0 ? "+" : ""}${t.static_score})`],
  ];
  dl.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(String(v))}</dd>`).join("");

  const pv = t.moves.find((m) => m.col === t.chosen)?.pv || [];
  pvEl.classList.toggle("hidden", !$("t-pv").checked || pv.length === 0);
  pvEl.textContent = "Expected line: " + pv.map((c) => c + 1).join(" → ")
    + (pv.length > 1 ? "  (numbers on the board show the order)" : "");
}

function setHover(col) {
  hoverCol = col;
  const ghosts = $("drop").children;
  const canPlay = state && !thinking && state.human_to_move;
  for (let c = 0; c < COLS; c++) {
    const on = canPlay && c === col && state.legal.includes(c);
    ghosts[c].className = "ghost" + (on ? ` on ${humanSymbol()}` : "");
  }
  document.querySelectorAll(".cell").forEach((el) => {
    el.classList.toggle("col-hover", canPlay && Number(el.dataset.col) === col);
  });
}

// ------------------------------------------------------------------ small helpers
function fillEngines(engines, def) {
  const sel = $("engine");
  const keep = sel.value;
  sel.innerHTML = "";
  for (const e of engines) {
    const o = document.createElement("option");
    o.value = e.id;
    o.textContent = e.label + (e.available ? "" : " (not ready)");
    o.disabled = !e.available;
    if (!e.available) o.title = e.why;
    sel.appendChild(o);
  }
  sel.value = engines.some((e) => e.id === keep && e.available) ? keep : def;
}

function addLog(q, a) {
  const log = $("log");
  const qe = document.createElement("div"); qe.className = "q"; qe.textContent = q;
  const ae = document.createElement("div"); ae.className = "a"; ae.textContent = a;
  log.append(qe, ae);
  log.scrollTop = log.scrollHeight;
}

function setConn(text, cls) { const el = $("conn"); el.textContent = text; el.className = "conn " + cls; }

let toastTimer = null;
function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 4500);
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

// ------------------------------------------------------------------ wire up
buildBoard();
$("new").addEventListener("click", newGame);
$("undo").addEventListener("click", () => send({ type: "undo" }));
["t-scores", "t-stats", "t-pv", "t-cells"].forEach((id) => $(id).addEventListener("change", render));
document.querySelectorAll(".quick button[data-q]").forEach((b) =>
  b.addEventListener("click", () => ask(b.dataset.q)));
$("q-whynot").addEventListener("click", () => ask(`Why not column ${$("q-col").value}?`));
$("q-whatif").addEventListener("click", () => ask(`What if I play column ${$("q-col").value}?`));
$("ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  ask($("ask").value);
  $("ask").value = "";
});
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= 7) play(n - 1);
});
render();
connect();
