package finops.enterprise;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

interface SecurityRepository extends JpaRepository<Security, String> {}

interface MarketCalendarDayRepository
    extends JpaRepository<MarketCalendarDay, MarketCalendarDayId> {}

/**
 * Query methods use explicit JPQL rather than derived-name traversal of the embedded id
 * (id.securityId / id.priceDate) — safer to get right without a compiler in this sandbox.
 * @Param names are given explicitly so this doesn't depend on -parameters at compile time.
 */
interface PriceRepository extends JpaRepository<Price, PriceId> {
  @Query("select p from Price p where p.id.securityId = :securityId order by p.id.priceDate desc")
  List<Price> findBySecurityIdOrderByPriceDateDesc(@Param("securityId") String securityId);

  default Optional<Price> findLatest(String securityId) {
    List<Price> rows = findBySecurityIdOrderByPriceDateDesc(securityId);
    return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
  }

  @Query("select p from Price p where p.id.securityId = :securityId and p.id.priceDate = :priceDate")
  Optional<Price> findOn(@Param("securityId") String securityId, @Param("priceDate") LocalDate priceDate);
}

interface BorrowAvailabilityRepository extends JpaRepository<BorrowAvailability, String> {}
