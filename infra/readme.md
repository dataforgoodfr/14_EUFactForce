## To-do

 - [ ] Créer via l'UI le bucket qui contient le state file
 - [ ] Créer le consumer OAuth1
 - [ ] Créer un passphrase pour l'encryption du state file - openssl rand -base64 32
 - [ ] Créer `secrets.auto.tfvars` à partir de `example.tfvars`
 - [ ] Remplacer les placeholders
 - [ ] Configurer les secrets github

## Test et dev en local

Afin de dev en local et tester les modifs avant de push, voici la séquence:

#### 0. Exporter les clefs du backend (clefs du Cellar de state) dans l'env.
`export AWS_ACCESS_KEY_ID="$TFSTATE_KEY_ID"`

`export AWS_SECRET_ACCESS_KEY="$TFSTATE_KEY_SECRET"`

#### 1. Vérifie le formatage
`tofu fmt -recursive`

`tofu init -backend=false`

`tofu validate`

#### 2. Init réel du backend (Cellar). -reconfigure car l'étape 1 a init sans backend.
`tofu init -reconfigure -backend-config=cellar.tfbackend`

#### 3. N'execute rien, donne le plan afin de voir ce qui est créé ou détruit.
`tofu plan -var-file=prod.tfvars`

#### 4. Executer le pre-commit
`pre-commit run --all-files`

/!\ pas de apply en local, la CI s'en charge

## Secrets à déclarer

### Dans `secrets.auto.tfvars`

Copié depuis `example.tfvars`, contient les 6 variables sensibles :

- `organisation`: orga_xxx (ou user_xxx)
- `cc_token`: jeton OAuth1 (`clever login`)
- `cc_secret`: secret OAuth1
- `cc_consumer_key`: clé du consumer dédié
- `cc_consumer_secret`: secret du consumer dédié
- `state_encryption_passphrase`: passphrase de chiffrement du state (>= 16 car.)

### Secrets GitHub (Environment `infra-apply`)

Pour la CI. Les identifiants du backend passent par les variables AWS standard :

- `TFSTATE_KEY_ID`: injecté en `AWS_ACCESS_KEY_ID` (clé du Cellar de state)
- `TFSTATE_KEY_SECRET`: injecté en `AWS_SECRET_ACCESS_KEY`
- `CC_ORGANISATION`, `CC_TOKEN`, `CC_SECRET`, `CC_CONSUMER_KEY`, `CC_CONSUMER_SECRET`: provider Clever Cloud
- `TF_STATE_PASSPHRASE`: chiffrement du state


## Placeholders à vérifier

- **`cellar.tfbackend`**: `endpoints.s3` (host réel du Cellar, ex. `cellar-c2.services.clever-cloud.com`) et `bucket` (nom du bucket de state créé à la main).
- **`prod.tfvars`**: `postgresql_plan` : `xxs_sml` mis par défaut, à tester.



## Fichiers

### versions.tf

Contient les versions requises du provider (Clever Cloud) et d'Open Tofu. la config partielle du backend S3 et le bloc d'encryption. Les coordonnées du bucket viennent de cellar.tfbackend.
Détermine l'algo d'encryption.
state_encryption_passphrase est lue depuis secrets.auto.tfvars, penser à l'initialiser.


### cellar.tfbackend

Contient les variables non sensibles du bucket de backend. Remplacer le contenu avec les bonnes valeurs.

Valeurs à remplacer:
 - endpoints, s3
 - bucket

Les identifiants (clés) ne sont PAS ici : ils passent par `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.

### provider.tf

Contient les tokens et secret qui permettent à open tofu de manipuler l'api (et donc créer les ressources).
Ces variables sont contenues dans secrets.auto.tfvars

### cellar.tf

Contient la config du cellar bucket applicatif.

### postgresql.tf

Contient la config pour la ressource postgresql.

### prod.tfvars

Contient les variables non sensibles pour définir la région, l'environnement ainsi que les variables pour postgresql et cellar. A passer avec `-var-file=prod.tfvars`.
Concernant postgresql, la plus petite instance possible hors dev a été mis par défaut. A tester!

### variables.tf

Définis les variables existantes, impose des contraintes sur celles-ci. déclare les variables sensibles afin qu'elles ne soient pas affichées.

### outputs.tf

Expose des valeurs générées par Tofu, accessibles hors du run. Les ouputs sensibles ne sont pas affichées en log.

### example.tfvars

ficher d'exemple pour générer secrets.auto.tfvars
