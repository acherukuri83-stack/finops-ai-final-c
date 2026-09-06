package finops.enterprise;

import java.time.LocalDateTime;

record RestrictionDto(
    String accountId, String type, String reason, String setBy, LocalDateTime setAt, Boolean active) {
  static RestrictionDto from(Restriction r) {
    return new RestrictionDto(r.accountId, r.type, r.reason, r.setBy, r.setAt, r.active);
  }
}

record ScreeningDto(String clientId, String status, LocalDateTime checkedAt) {
  static ScreeningDto from(ScreeningResult s) {
    return new ScreeningDto(s.clientId, s.status, s.checkedAt);
  }
}
