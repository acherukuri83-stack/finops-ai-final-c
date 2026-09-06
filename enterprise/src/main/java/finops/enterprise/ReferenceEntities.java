package finops.enterprise;

import jakarta.persistence.Column;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Embeddable;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * `securities`, `market_calendar`, `prices`, `borrow_availability` — see
 * V2__phase_a_schema.sql.
 */
@Entity
@Table(name = "securities")
class Security {
  @Id
  @Column(name = "security_id")
  String securityId;

  String isin;
  String cusip;
  String description;

  @Column(name = "settle_cycle")
  String settleCycle;

  String status;

  protected Security() {}
}

@Embeddable
class MarketCalendarDayId implements Serializable {
  String market;

  @Column(name = "calendar_date")
  LocalDate calendarDate;

  protected MarketCalendarDayId() {}

  MarketCalendarDayId(String market, LocalDate calendarDate) {
    this.market = market;
    this.calendarDate = calendarDate;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof MarketCalendarDayId that)) return false;
    return Objects.equals(market, that.market) && Objects.equals(calendarDate, that.calendarDate);
  }

  @Override
  public int hashCode() {
    return Objects.hash(market, calendarDate);
  }
}

@Entity
@Table(name = "market_calendar")
class MarketCalendarDay {
  @EmbeddedId MarketCalendarDayId id;

  @Column(name = "is_business_day")
  Boolean isBusinessDay;

  @Column(name = "holiday_name")
  String holidayName;

  protected MarketCalendarDay() {}
}

@Embeddable
class PriceId implements Serializable {
  @Column(name = "security_id")
  String securityId;

  @Column(name = "price_date")
  LocalDate priceDate;

  protected PriceId() {}

  PriceId(String securityId, LocalDate priceDate) {
    this.securityId = securityId;
    this.priceDate = priceDate;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof PriceId that)) return false;
    return Objects.equals(securityId, that.securityId) && Objects.equals(priceDate, that.priceDate);
  }

  @Override
  public int hashCode() {
    return Objects.hash(securityId, priceDate);
  }
}

@Entity
@Table(name = "prices")
class Price {
  @EmbeddedId PriceId id;

  @Column(name = "close_price")
  BigDecimal closePrice;

  protected Price() {}
}

@Entity
@Table(name = "borrow_availability")
class BorrowAvailability {
  @Id
  @Column(name = "security_id")
  String securityId;

  @Column(name = "available_qty")
  Long availableQty;

  BigDecimal rate;

  @JdbcTypeCode(SqlTypes.JSON)
  List<Map<String, Object>> recalls;

  protected BorrowAvailability() {}
}
