package finops.enterprise;

import java.math.BigDecimal;
import java.time.LocalDate;

record SecurityDto(
    String securityId, String ticker, String isin, String cusip, String description, String settleCycle, String status) {
  static SecurityDto from(Security s) {
    return new SecurityDto(s.securityId, s.securityId, s.isin, s.cusip, s.description, s.settleCycle, s.status);
  }
}

record CalendarDayDto(String market, LocalDate calendarDate, Boolean isBusinessDay, String holidayName) {
  static CalendarDayDto from(MarketCalendarDay d) {
    return new CalendarDayDto(d.id.market, d.id.calendarDate, d.isBusinessDay, d.holidayName);
  }
}

record PriceDto(String securityId, LocalDate priceDate, BigDecimal closePrice) {
  static PriceDto from(Price p) {
    return new PriceDto(p.id.securityId, p.id.priceDate, p.closePrice);
  }
}
