package finops.enterprise;

import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

interface ClientRepository extends JpaRepository<Client, String> {}

interface AccountRepository extends JpaRepository<Account, String> {
  List<Account> findByClientId(String clientId);
}
