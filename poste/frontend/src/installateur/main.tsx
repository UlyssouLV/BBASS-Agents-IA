import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AssistantInstallation } from "@/installateur/AssistantInstallation";

import "../index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AssistantInstallation />
  </StrictMode>
);
