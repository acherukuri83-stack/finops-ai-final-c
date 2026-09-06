package finops.enterprise;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
class ComplianceController {
  private final RestrictionRepository restrictions;
  private final ScreeningResultRepository screening;

  ComplianceController(RestrictionRepository restrictions, ScreeningResultRepository screening) {
    this.restrictions = restrictions;
    this.screening = screening;
  }

  @GetMapping("/restrictions")
  List<RestrictionDto> getRestrictions(@RequestParam String account) {
    return restrictions.findByAccountIdAndActiveTrue(account).stream().map(RestrictionDto::from).toList();
  }

  @GetMapping("/screening")
  ScreeningDto getScreening(@RequestParam String client) {
    return screening
        .findById(client)
        .map(ScreeningDto::from)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, client));
  }
}
