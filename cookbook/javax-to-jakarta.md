# javax → jakarta namespace migration

For Jakarta EE 9+ (and Spring Boot 3+, Hibernate 6+, …), all `javax.*` enterprise namespaces moved to `jakarta.*`.

This is the single most mechanical and the single most error-prone migration step:
- Mechanical because it is literally a namespace rename across thousands of imports.
- Error-prone because **not every `javax.*` package moved**. `javax.crypto`, `javax.net`, `javax.sql` are JDK packages and DO NOT change.

## Rules (high confidence — agent may apply without human review)

| Old prefix | New prefix |
|------------|-----------|
| `javax.servlet` | `jakarta.servlet` |
| `javax.servlet.http` | `jakarta.servlet.http` |
| `javax.persistence` | `jakarta.persistence` |
| `javax.validation` | `jakarta.validation` |
| `javax.annotation.security` | `jakarta.annotation.security` |
| `javax.annotation.Resource` | `jakarta.annotation.Resource` |
| `javax.annotation.PostConstruct` | `jakarta.annotation.PostConstruct` |
| `javax.annotation.PreDestroy` | `jakarta.annotation.PreDestroy` |
| `javax.ejb` | `jakarta.ejb` |
| `javax.enterprise` | `jakarta.enterprise` |
| `javax.faces` | `jakarta.faces` |
| `javax.inject` | `jakarta.inject` |
| `javax.jms` | `jakarta.jms` |
| `javax.json` | `jakarta.json` |
| `javax.mail` | `jakarta.mail` |
| `javax.transaction.Transactional` | `jakarta.transaction.Transactional` |
| `javax.ws.rs` | `jakarta.ws.rs` |
| `javax.xml.bind` | `jakarta.xml.bind` |
| `javax.xml.ws` | `jakarta.xml.ws` |

## Do NOT rewrite (these stay in `javax.*` — they are JDK packages)

- `javax.crypto`
- `javax.net`, `javax.net.ssl`
- `javax.sql` (JDBC DataSource — note: `javax.sql.DataSource` stays)
- `javax.security.auth` (JAAS — but `javax.security.auth.message` → `jakarta.security.auth.message`)
- `javax.naming` (JNDI)
- `javax.management` (JMX)
- `javax.script`
- `javax.swing`, `javax.imageio`, `javax.sound`
- `javax.print`
- `javax.lang.model`
- `javax.tools`
- `javax.smartcardio`
- `javax.xml.parsers`, `javax.xml.transform`, `javax.xml.stream`, `javax.xml.xpath`, `javax.xml.namespace` (these are JDK XML, not JAX-WS/JAXB)
- `javax.xml.datatype`, `javax.xml.validation`

## Notes

- `javax.transaction` has BOTH paths: the JTA bits moved to `jakarta.transaction`, but the JTA spec lives there. `javax.transaction.xa` (JDBC XA) is JDK and stays in `javax.transaction.xa`.
- `javax.activation` → `jakarta.activation` for JavaMail uses; if you only depend on the JAF type, it moved.
- `pom.xml` / `build.gradle` dependency coordinates also change (e.g. `javax.servlet:javax.servlet-api` → `jakarta.servlet:jakarta.servlet-api`). The build file rewrite is a separate cookbook entry.

**Confidence**: high for the rules above; **medium** for `javax.transaction` and `javax.activation` edge cases — flag for human review when those appear.

**Last updated**: 2026-05-15.
