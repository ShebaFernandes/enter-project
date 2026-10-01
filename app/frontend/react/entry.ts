// Foundation exports only. No production page is registered or mounted in FM2.
import "./foundation.css";
export * from "./components";
export * from "./mount";
export { sameOriginClient, responseJson, ApiError } from "../shared/api-client";
