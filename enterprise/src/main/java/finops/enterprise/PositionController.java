package finops.enterprise;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
class PositionController {
  private final PositionRepository positions;
  private final BorrowAvailabilityRepository borrow;

  PositionController(PositionRepository positions, BorrowAvailabilityRepository borrow) {
    this.positions = positions;
    this.borrow = borrow;
  }

  @GetMapping("/positions")
  Object getPositions(
      @RequestParam String account, @RequestParam(required = false) String security) {
    if (security != null) {
      return positions
          .findLatest(account, security)
          .map(PositionDto::from)
          .orElseThrow(
              () ->
                  new ResponseStatusException(
                      HttpStatus.NOT_FOUND, "no position for " + account + "/" + security));
    }
    List<PositionDto> latestPerSecurity =
        positions.findAllForAccount(account).stream()
            .collect(
                java.util.stream.Collectors.toMap(
                    p -> p.id.securityId, PositionDto::from, (a, b) -> a, java.util.LinkedHashMap::new))
            .values()
            .stream()
            .toList();
    return latestPerSecurity;
  }

  @GetMapping("/borrow/{security}")
  BorrowAvailabilityDto getBorrow(@PathVariable String security) {
    return borrow
        .findById(security)
        .map(BorrowAvailabilityDto::from)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, security));
  }
}
