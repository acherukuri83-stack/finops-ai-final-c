package finops.enterprise;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/**
 * /trades endpoints. Write endpoints (resubmit, cancel) take no approval logic — the MCP write
 * tools (resubmit_settlement, cancel_trade) own approval validation in W3. This tier just
 * performs the mutation and records it.
 */
@RestController
class TradeController {
  private final TradeRepository trades;
  private final SettlementAttemptRepository attempts;
  private final AffirmationRepository affirmations;

  TradeController(
      TradeRepository trades, SettlementAttemptRepository attempts, AffirmationRepository affirmations) {
    this.trades = trades;
    this.attempts = attempts;
    this.affirmations = affirmations;
  }

  @GetMapping("/trades/{id}")
  TradeDto get(@PathVariable String id) {
    return TradeDto.from(require(id));
  }

  @GetMapping("/trades")
  List<TradeDto> find(
      @RequestParam(required = false) String client,
      @RequestParam(required = false) String account,
      @RequestParam(required = false) String status,
      @RequestParam(required = false) String security,
      @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate tradeDate,
      @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate settleDate) {
    Specification<Trade> spec = Specification.where(null);
    if (client != null) spec = spec.and((r, q, cb) -> cb.equal(r.get("clientId"), client));
    if (account != null) spec = spec.and((r, q, cb) -> cb.equal(r.get("accountId"), account));
    if (status != null) spec = spec.and((r, q, cb) -> cb.equal(r.get("status"), status));
    if (security != null) spec = spec.and((r, q, cb) -> cb.equal(r.get("securityId"), security));
    if (tradeDate != null) spec = spec.and((r, q, cb) -> cb.equal(r.get("tradeDate"), tradeDate));
    if (settleDate != null) spec = spec.and((r, q, cb) -> cb.equal(r.get("settleDate"), settleDate));
    return trades.findAll(spec).stream().map(TradeDto::from).toList();
  }

  @GetMapping("/trades/{id}/settlement")
  SettlementStatusDto settlement(@PathVariable String id) {
    Trade t = require(id);
    List<SettlementAttempt> attemptRows = attempts.findByTradeIdOrderByAtAsc(id);
    Optional<SettlementAttempt> last = attemptRows.isEmpty()
        ? Optional.empty()
        : Optional.of(attemptRows.get(attemptRows.size() - 1));
    return new SettlementStatusDto(
        t.tradeId,
        t.status,
        t.failureCode,
        last.map(a -> a.detail).orElse(null),
        attemptRows.stream().map(AttemptDto::from).toList(),
        last.map(a -> a.at).orElse(null));
  }

  @GetMapping("/trades/{id}/affirmation")
  AffirmationDto affirmation(@PathVariable String id) {
    require(id); // 404s if the trade itself doesn't exist
    return affirmations
        .findFirstByTradeIdOrderByAffirmedAtDesc(id)
        .map(AffirmationDto::from)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "no affirmation for " + id));
  }

  @PostMapping("/trades/{id}/resubmit")
  ResubmitResponseDto resubmit(@PathVariable String id, @RequestBody(required = false) ResubmitRequest body) {
    require(id);
    SettlementAttempt a = new SettlementAttempt();
    a.tradeId = id;
    a.at = LocalDateTime.now();
    a.result = "SUBMITTED";
    a.detail = body != null && body.note() != null ? body.note() : "resubmitted via API";
    attempts.save(a);
    return new ResubmitResponseDto(id, "SUBMITTED", AttemptDto.from(a));
  }

  @PostMapping("/trades/{id}/cancel")
  CancelResponseDto cancel(@PathVariable String id, @RequestBody CancelRequest body) {
    Trade t = require(id);
    t.status = "CANCELLED";
    trades.save(t);
    return new CancelResponseDto(id, t.status, body.reason());
  }

  private Trade require(String id) {
    return trades.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, id));
  }
}
