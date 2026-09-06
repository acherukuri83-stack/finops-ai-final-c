package finops.enterprise;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

interface SsiVersionRepository extends JpaRepository<SsiVersion, Long> {
  List<SsiVersion> findByAccountIdOrderByVersionAsc(String accountId);

  Optional<SsiVersion> findFirstByAccountIdOrderByVersionDesc(String accountId);
}

interface CounterpartySsiRepository extends JpaRepository<CounterpartySsi, Long> {
  Optional<CounterpartySsi> findFirstByCptyIdOrderByIdDesc(String cptyId);
}
