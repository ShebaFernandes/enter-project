// Each registered page still requires its own default-off server flag.
import "./foundation";
import "./chooser.css";
import { PlatformChooser } from "./chooser";
import { SearchHome } from "./search-home";
import "./search-home.css";
import { CriteriaReview } from "./criteria-review";
import "./criteria-review.css";
import { mountPage } from "./mount";
export * from "./foundation";

if (document.querySelector("[data-react-page]")) {
  void mountPage({
    chooser: PlatformChooser,
    "search-home": SearchHome,
    "criteria-review": CriteriaReview,
  }).catch(() => {
    document.querySelector<HTMLElement>("[data-page-fallback]")?.focus();
  });
}
