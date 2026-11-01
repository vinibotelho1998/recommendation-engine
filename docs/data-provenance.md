# Proveniência e contrato dos dados

## Fixture incluída

`data/demo/movies.csv` e `ratings.csv` foram gerados por `recommendation_engine.data.generate_demo`, seed 42. São 120 usuários fictícios, 72 filmes fictícios, seis grupos de preferência e 1.440 avaliações. Não há nomes ou hábitos de pessoas reais.

As preferências são deliberadamente bem separadas: nove filmes positivos no grupo principal e três avaliações baixas fora dele por usuário. O propósito é verificar o pipeline com sinal conhecido. Os dados gerados desta fixture estão disponíveis sob CC0-1.0; essa indicação não se estende a outras bases.

## MovieLens opcional

Fonte: GroupLens, University of Minnesota, [MovieLens latest datasets](https://grouplens.org/datasets/movielens/latest/).

O projeto fornece um downloader para o arquivo `ml-latest-small.zip`, mas não inclui nem redistribui esse conteúdo. Leia os termos no [README original](https://files.grouplens.org/datasets/movielens/ml-latest-small-README.html). A execução exige `--accept-license`; isso registra o aceite do operador do comando, não altera os termos da fonte.

O download preserva `README.txt` e registra origem, instante e SHA-256 do arquivo em `provenance.json`. A extração lê apenas `movies.csv`, `ratings.csv` e `README.txt`, sem usar caminhos arbitrários do ZIP. Há limites de tamanho e validação do dataset antes de movê-lo ao destino final.

## Outros CSVs

O diretório fornecido em `--data` deve conter:

```text
movies.csv: movieId,title[,genres]
ratings.csv: userId,movieId,rating,timestamp
```

IDs devem ser inteiros positivos. Notas devem estar entre 0,5 e 5, em intervalos de 0,5. Timestamps são inteiros positivos em segundos Unix. O catálogo deve ter IDs únicos e títulos preenchidos. Eventos não podem apontar para filmes ausentes do catálogo. Pares usuário/filme duplicados são rejeitados: resolva as atualizações antes da importação, conforme uma política explícita.

Para preservar a avaliação temporal, não substitua timestamps ausentes pela data atual. O leitor falha em dados inválidos em vez de corrigir silenciosamente o histórico. Datas de inclusão dos filmes não fazem parte desse contrato; a avaliação considera o catálogo inteiro disponível.
