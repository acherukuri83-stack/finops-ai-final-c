# portal — conventions
- React 18 + TypeScript strict + Vite. Functional components only.
- No global state library until two screens share server state.
- API client generated from platform-api's OpenAPI (W1 PR3 adds the generator).
- Show the trace id wherever a request result is shown.
