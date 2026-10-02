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
import { CandidateProfilePage } from "./candidate-profile";
import "./candidate-profile.css";
import { JobsDirectory, RolePage } from "./public-opportunities";
import "./public-opportunities.css";
import { CandidateProgress } from "./candidate-progress";
import { CandidateRights } from "./candidate-rights";
import "./candidate-control.css";
import { OrganizationPage } from "./recruiter-organization";
import "./recruiter-organization.css";
export * from "./foundation";

if (document.querySelector("[data-react-page]")) {
  void mountPage({
    chooser: PlatformChooser,
    "search-home": SearchHome,
    "criteria-review": CriteriaReview,
    "search-results": SearchResults,
    "candidate-management": CandidateManagement,
    "candidate-comparison": CandidateComparison,
    "candidate-profile": CandidateProfilePage,
    "public-jobs": JobsDirectory,
    "public-role": RolePage,
    "candidate-progress": CandidateProgress,
    "candidate-rights": CandidateRights,
    "recruiter-organization": OrganizationPage,
  }).catch(() => {
    document.querySelector<HTMLElement>("[data-page-fallback]")?.focus();
  });
}
