package finops.enterprise;

import java.time.LocalDateTime;
import java.util.List;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** /logs — newest first, capped at 50 to match ops-server's search_logs contract. */
@RestController
class LogController {
  private static final int MAX_RESULTS = 50;

  private final AppLogRepository logs;

  LogController(AppLogRepository logs) {
    this.logs = logs;
  }

  @GetMapping("/logs")
  List<LogEntryDto> search(
      @RequestParam(required = false) String q,
      @RequestParam(required = false) String tradeId,
      @RequestParam(required = false) String system,
      @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime from,
      @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime to) {
    Specification<AppLog> spec = Specification.where(null);
    if (q != null) spec = spec.and((r, cq, cb) -> cb.like(cb.lower(r.get("msg")), "%" + q.toLowerCase() + "%"));
    if (tradeId != null) spec = spec.and((r, cq, cb) -> cb.equal(r.get("tradeId"), tradeId));
    if (system != null) spec = spec.and((r, cq, cb) -> cb.equal(r.get("svc"), system));
    if (from != null) spec = spec.and((r, cq, cb) -> cb.greaterThanOrEqualTo(r.get("ts"), from));
    if (to != null) spec = spec.and((r, cq, cb) -> cb.lessThanOrEqualTo(r.get("ts"), to));
    return logs
        .findAll(spec, PageRequest.of(0, MAX_RESULTS, Sort.by(Sort.Direction.DESC, "ts")))
        .stream()
        .map(LogEntryDto::from)
        .toList();
  }
}
