package finops.enterprise;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

record PositionDto(
    String accountId,
    String securityId,
    LocalDate asOf,
    Long qty,
    Long available,
    Long pendingDeliver,
    Long pendingReceive) {
  static PositionDto from(Position p) {
    return new PositionDto(
        p.id.accountId, p.id.securityId, p.id.asOf, p.qty, p.available, p.pendingDeliver, p.pendingReceive);
  }
}

record BorrowAvailabilityDto(
    String securityId, Long availableQty, java.math.BigDecimal rate, List<Map<String, Object>> recalls) {
  static BorrowAvailabilityDto from(BorrowAvailability b) {
    return new BorrowAvailabilityDto(b.securityId, b.availableQty, b.rate, b.recalls);
  }
}
