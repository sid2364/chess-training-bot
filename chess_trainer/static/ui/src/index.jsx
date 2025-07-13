import React from "react";
import { createRoot } from "react-dom/client";
import OpeningsTree from "./OpeningsTree";

const container = document.getElementById("react-root");
const root = createRoot(container);
root.render(
  <>
    <OpeningsTree side="white" />
    <OpeningsTree side="black" />
  </>
);
