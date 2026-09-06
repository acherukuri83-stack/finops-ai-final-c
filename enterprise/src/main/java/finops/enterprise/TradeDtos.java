package finops.enterprise;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Field names match docs/tool-contracts.md's Trade / SettlementStatus shapes exactly; Jackson's
 * SNAKE_CASE naming strategy (application.yml) turns e.g. tradeId -> trade_id on the wire.
 */
record TradeDto(
    String tradeId,
    String clientId,
    String accountId,
    String securityId,
    Long qty,
    String side,
    BigDecimal price,
    LocalDate tradeDate,
    LocalDate settleDate,
    String status,
    String cptyId,
    LocalDateTime bookedAt) {

  static TradeDto from(Trade t) {
    return new TradeDto(
        t.tradeId,
        t.clientId,
        t.accountId,
        t.securityId,
        t.qty,
        t.side,
        t.price,
        t.tradeDate,
        t.settleDate,
        t.status,
        t.cptyId,
        t.bookedAt);
  }
}

record AttemptDto(LocalDateTime at, String result, String detail) {
  static AttemptDto from(SettlementAttempt a) {
    return new AttemptDto(a.at, a.result, a.detail);
  }
}

record SettlementStatusDto(
    String tradeId,
    String status,
    String failureCode,
    String failureDetail,
    List<AttemptDto> attempts,
    LocalDateTime lastAttemptAt) {}

record ResubmitRequest(String note) {}

record ResubmitResponseDto(String tradeId, String result, AttemptDto attempt) {}

record CancelRequest(String reason) {}

record CancelResponseDto(String tradeId, String status, String reason) {}
