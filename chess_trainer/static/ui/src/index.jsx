import React from "react";
import { createRoot } from "react-dom/client";
import OpeningsTree from "./OpeningsTree";

const root = createRoot(document.getElementById("react-root"));
root.render(<OpeningsTree />);
