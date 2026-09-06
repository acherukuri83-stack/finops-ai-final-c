package finops.enterprise;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

/** find_trades' filters (all optional) are applied via JpaSpecificationExecutor. */
interface TradeRepository extends JpaRepository<Trade, String>, JpaSpecificationExecutor<Trade> {}

interface SettlementAttemptRepository extends JpaRepository<SettlementAttempt, Long> {
  List<SettlementAttempt> findByTradeIdOrderByAtAsc(String tradeId);
}

interface AffirmationRepository extends JpaRepository<Affirmation, Long> {
  Optional<Affirmation> findFirstByTradeIdOrderByAffirmedAtDesc(String tradeId);
}
