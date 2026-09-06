package finops.enterprise;

import java.time.LocalDateTime;

record LogEntryDto(LocalDateTime ts, String svc, String level, String msg, String tradeId) {
  static LogEntryDto from(AppLog l) {
    return new LogEntryDto(l.ts, l.svc, l.level, l.msg, l.tradeId);
  }
}
