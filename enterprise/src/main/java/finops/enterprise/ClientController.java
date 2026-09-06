package finops.enterprise;

import java.time.LocalDateTime;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/** /clients and /accounts endpoints, including SSI. */
@RestController
class ClientController {
  private final ClientRepository clients;
  private final AccountRepository accounts;
  private final SsiVersionRepository ssiVersions;
  private final RestrictionRepository restrictions;

  ClientController(
      ClientRepository clients,
      AccountRepository accounts,
      SsiVersionRepository ssiVersions,
      RestrictionRepository restrictions) {
    this.clients = clients;
    this.accounts = accounts;
    this.ssiVersions = ssiVersions;
    this.restrictions = restrictions;
  }

  @GetMapping("/clients/{id}")
  ClientDto getClient(@PathVariable String id) {
    Client c = clients.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, id));
    List<String> accountIds = accounts.findByClientId(id).stream().map(a -> a.accountId).toList();
    List<RestrictionDto> rs =
        restrictions.findByAccountIdInAndActiveTrue(accountIds).stream().map(RestrictionDto::from).toList();
    return new ClientDto(c.clientId, c.name, c.type, c.status, rs);
  }

  @GetMapping("/accounts/{id}")
  AccountDto getAccount(@PathVariable String id) {
    Account a = requireAccount(id);
    List<RestrictionDto> rs =
        restrictions.findByAccountIdAndActiveTrue(id).stream().map(RestrictionDto::from).toList();
    // riskFlags[] has no backing data in the Phase A schema — always empty. See ClientDtos.java.
    return new AccountDto(a.accountId, a.clientId, a.custodian, a.status, rs, List.of());
  }

  @GetMapping("/accounts/{id}/ssi")
  SsiDto currentSsi(@PathVariable String id) {
    requireAccount(id);
    return ssiVersions
        .findFirstByAccountIdOrderByVersionDesc(id)
        .map(SsiDto::from)
        .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "no SSI for " + id));
  }

  @GetMapping("/accounts/{id}/ssi/history")
  List<SsiDto> ssiHistory(@PathVariable String id) {
    requireAccount(id);
    return ssiVersions.findByAccountIdOrderByVersionAsc(id).stream().map(SsiDto::from).toList();
  }

  @PutMapping("/accounts/{id}/ssi")
  SsiDto updateSsi(@PathVariable String id, @RequestBody SsiUpdateRequest body) {
    requireAccount(id);
    int nextVersion =
        ssiVersions.findFirstByAccountIdOrderByVersionDesc(id).map(v -> v.version + 1).orElse(1);
    // Close out the prior current version (if any) so history stays contiguous.
    ssiVersions
        .findFirstByAccountIdOrderByVersionDesc(id)
        .filter(v -> v.validTo == null)
        .ifPresent(
            v -> {
              v.validTo = body.validFrom().minusDays(1);
              ssiVersions.save(v);
            });
    SsiVersion v = new SsiVersion();
    v.accountId = id;
    v.version = nextVersion;
    v.dtcParticipant = body.dtcParticipant();
    v.agentBic = body.agentBic();
    v.validFrom = body.validFrom();
    v.validTo = null;
    v.updatedAt = LocalDateTime.now();
    v.updatedBy = body.updatedBy() != null ? body.updatedBy() : "ops.api";
    return SsiDto.from(ssiVersions.save(v));
  }

  private Account requireAccount(String id) {
    return accounts.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, id));
  }
}
