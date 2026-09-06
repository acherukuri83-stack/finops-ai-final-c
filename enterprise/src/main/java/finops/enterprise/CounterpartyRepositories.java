package finops.enterprise;

import org.springframework.data.jpa.repository.JpaRepository;

interface CounterpartyRepository extends JpaRepository<Counterparty, String> {}
