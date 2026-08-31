import React from "react";
import { createRoot } from "react-dom/client";
import SetupBody from "./SetupBody";

const el = document.getElementById("react-root");
const stateTag = document.getElementById("initial-state");
let initial = { challenge: 0, username: "", allowAll: false, color: "random" };
try {
  if (stateTag) initial = { ...initial, ...JSON.parse(stateTag.textContent) };
} catch (e) {
  console.warn("Could not read initial state", e);
}

createRoot(el).render(<SetupBody initial={initial} />);
