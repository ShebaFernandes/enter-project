// Server flags select chooser/search home only; review/results/comparison stay legacy.
import "./foundation";
import "./chooser.css";
import { PlatformChooser } from "./chooser";
import { SearchHome } from "./search-home";
import "./search-home.css";
import { mountPage } from "./mount";
export * from "./foundation";

if (document.querySelector("[data-react-page]")) {
  void mountPage({ chooser: PlatformChooser, "search-home": SearchHome }).catch(
    () => {
      document.querySelector<HTMLElement>("[data-page-fallback]")?.focus();
    },
  );
}
