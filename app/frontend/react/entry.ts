// Only FM3's reviewed public chooser is registered; workflow pages stay legacy.
import "./foundation";
import "./chooser.css";
import { PlatformChooser } from "./chooser";
import { mountPage } from "./mount";
export * from "./foundation";

if (document.querySelector("[data-react-page]")) {
  void mountPage({ chooser: PlatformChooser }).catch(() => {
    document.querySelector<HTMLElement>("[data-page-fallback]")?.focus();
  });
}
