package finops.enterprise;

import java.time.LocalDate;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
class ReferenceController {
  private final SecurityRepository securities;
  private final MarketCalendarDayRepository calendar;

  ReferenceController(SecurityRepository securities, MarketCalendarDayRepository calendar) {
    this.securities = securities;
    this.calendar = calendar;
  }

  @GetMapping("/securities/{id}")
  SecurityDto get(@PathVariable String id) {
    return securities
        .findById(id)
        .map(SecurityDto::from)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, id));
  }

  @GetMapping("/calendar")
  CalendarDayDto getCalendar(
      @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
      @RequestParam String market) {
    return calendar
        .findById(new MarketCalendarDayId(market, date))
        .map(CalendarDayDto::from)
        .orElseThrow(
            () -> new ResponseStatusException(HttpStatus.NOT_FOUND, market + "@" + date));
  }
}
