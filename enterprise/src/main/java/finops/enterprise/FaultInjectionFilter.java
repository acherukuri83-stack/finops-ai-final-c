package finops.enterprise;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * FAULT_INJECT=trade.settlement_status:503 makes GET /trades/{id}/settlement return 503.
 * Used by eval scenario 12. Format: comma-separated "<route-key>:<status>".
 */
@Component
public class FaultInjectionFilter extends OncePerRequestFilter {
  private final Set<String> rules;

  public FaultInjectionFilter(@Value("${FAULT_INJECT:}") String faultInject) {
    this.rules = faultInject.isBlank() ? Set.of() : Set.of(faultInject.split(","));
  }

  @Override
  protected void doFilterInternal(
      HttpServletRequest req, HttpServletResponse res, FilterChain chain)
      throws ServletException, IOException {
    String key = routeKey(req);
    for (String rule : rules) {
      String[] parts = rule.split(":");
      if (parts.length == 2 && parts[0].equals(key)) {
        res.setStatus(Integer.parseInt(parts[1]));
        res.setContentType("application/json");
        res.getWriter().write("{\"error\":\"fault injected\",\"retryable\":true}");
        return;
      }
    }
    chain.doFilter(req, res);
  }

  private static String routeKey(HttpServletRequest req) {
    String p = req.getRequestURI();
    if (p.matches("/trades/[^/]+/settlement")) return "trade.settlement_status";
    return "";
  }
}
