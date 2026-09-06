package finops.enterprise;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

/** /logs' filters (q, tradeId, system, from, to) are applied via JpaSpecificationExecutor. */
interface AppLogRepository extends JpaRepository<AppLog, Long>, JpaSpecificationExecutor<AppLog> {}
