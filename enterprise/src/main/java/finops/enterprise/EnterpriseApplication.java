package finops.enterprise;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** Simulated bank estate. Plain REST over JPA; no AI, MCP, or agent code in this tier. */
@SpringBootApplication
public class EnterpriseApplication {
  public static void main(String[] args) {
    SpringApplication.run(EnterpriseApplication.class, args);
  }
}
