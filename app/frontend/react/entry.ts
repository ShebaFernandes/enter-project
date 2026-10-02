// Each registered page still requires its own default-off server flag.
import "./foundation";
import "./chooser.css";
import { PlatformChooser } from "./chooser";
import { SearchHome } from "./search-home";
import "./search-home.css";
import { CriteriaReview } from "./criteria-review";
import "./criteria-review.css";
import { SearchResults } from "./search-results";
import "./search-results.css";
import { mountPage } from "./mount";
import { CandidateManagement } from "./candidate-management";
import { CandidateComparison } from "./candidate-comparison";
import "./candidate-comparison.css";
export * from "./foundation";

if (document.querySelector("[data-react-page]")) {
  void mountPage({
    chooser: PlatformChooser,
    "search-home": SearchHome,
    "criteria-review": CriteriaReview,
    "search-results": SearchResults,
    "candidate-management": CandidateManagement,
    "candidate-comparison": CandidateComparison,
  }).catch(() => {
    document.querySelector<HTMLElement>("[data-page-fallback]")?.focus();
  });
}
