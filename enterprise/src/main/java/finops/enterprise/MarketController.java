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
class MarketController {
  private final PriceRepository prices;

  MarketController(PriceRepository prices) {
    this.prices = prices;
  }

  @GetMapping("/prices/{security}")
  PriceDto get(
      @PathVariable String security,
      @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate asOf) {
    var found = asOf != null ? prices.findOn(security, asOf) : prices.findLatest(security);
    return found
        .map(PriceDto::from)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, security));
  }
}
