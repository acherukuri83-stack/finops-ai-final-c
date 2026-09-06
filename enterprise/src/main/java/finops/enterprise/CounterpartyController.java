package finops.enterprise;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
class CounterpartyController {
  private final CounterpartyRepository counterparties;
  private final CounterpartySsiRepository ssi;

  CounterpartyController(CounterpartyRepository counterparties, CounterpartySsiRepository ssi) {
    this.counterparties = counterparties;
    this.ssi = ssi;
  }

  @GetMapping("/counterparties/{id}")
  CounterpartyDto get(@PathVariable String id) {
    Counterparty c =
        counterparties.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, id));
    // contacts[] has no backing data in the Phase A schema — always empty. See CounterpartyDtos.java.
    return new CounterpartyDto(c.cptyId, c.name, c.status, java.util.List.of());
  }

  @GetMapping("/counterparties/{id}/ssi")
  CptySsiDto getSsi(@PathVariable String id) {
    if (!counterparties.existsById(id)) throw new ResponseStatusException(HttpStatus.NOT_FOUND, id);
    return ssi.findFirstByCptyIdOrderByIdDesc(id)
        .map(CptySsiDto::from)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "no SSI on file for " + id));
  }
}
