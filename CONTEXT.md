# Vina Bim Shop data operations

The project concerns an internal analyst's understanding of marketplace data and changes in its customer behavior measures.

## Language

**Data operations assistant**:
An assistant that helps an analyst consult metric definitions, data contracts and operational runbooks, and investigate measured changes in the corresponding data.
_Avoid_: Customer policy support assistant

**Analyst**:
The internal user investigating the meaning, quality and changing behavior of marketplace data.
_Avoid_: Shopper, customer support chatbot user

**Customer order frequency**:
A measure of how often a customer places orders within a stated observation window. The eligible orders, population and window are part of its metric definition.
_Avoid_: Lifetime order count, unless that is the explicitly chosen measure

**Data drift**:
A measured difference in a data distribution between a baseline and a later comparison period. It does not by itself establish a cause or a predictive model's performance.
_Avoid_: Root cause, model failure

**Operational knowledge**:
Metric definitions, data contracts and runbooks that explain how an analyst should understand and investigate the marketplace data.
_Avoid_: Customer policy corpus
