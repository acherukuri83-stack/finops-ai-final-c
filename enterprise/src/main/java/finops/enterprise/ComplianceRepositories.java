package finops.enterprise;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * Position queries use explicit JPQL rather than derived-name traversal of the embedded id —
 * safer to get right without a compiler in this sandbox.
 */
interface PositionRepository extends JpaRepository<Position, PositionId> {
  @Query(
      "select p from Position p where p.id.accountId = :accountId and p.id.securityId = :securityId "
          + "order by p.id.asOf desc")
  List<Position> findByAccountAndSecurityOrderByAsOfDesc(
      @Param("accountId") String accountId, @Param("securityId") String securityId);

  default Optional<Position> findLatest(String accountId, String securityId) {
    List<Position> rows = findByAccountAndSecurityOrderByAsOfDesc(accountId, securityId);
    return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
  }

  @Query("select p from Position p where p.id.accountId = :accountId order by p.id.securityId asc, p.id.asOf desc")
  List<Position> findAllForAccount(@Param("accountId") String accountId);
}

interface RestrictionRepository extends JpaRepository<Restriction, Long> {
  List<Restriction> findByAccountIdAndActiveTrue(String accountId);

  List<Restriction> findByAccountIdInAndActiveTrue(List<String> accountIds);
}

interface ScreeningResultRepository extends JpaRepository<ScreeningResult, String> {}
