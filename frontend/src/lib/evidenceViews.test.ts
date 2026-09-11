import { describe, expect, it } from "vitest";
import { sharedPathways, targetJoins } from "./evidenceViews";
import type { EvidenceGraph } from "../api/types";

/** Shaped like a real `/candidate/graph` response: one gene-target join and
 * one shared pathway, each carrying the provenance the backend attaches. */
function graph(overrides: Partial<EvidenceGraph> = {}): EvidenceGraph {
  return {
    disease_id: "DIS:000007",
    disease_name: "asthma",
    drug_id: "DRUG:000197",
    drug_ids: ["DRUG:000197"],
    nodes: [
      { id: "disease:DIS:000007", type: "disease", label: "asthma", metadata: {} },
      { id: "drug:DRUG:000197", type: "drug", label: "celiprolol", metadata: {} },
      {
        id: "disease_gene:GENE:000873",
        type: "disease_gene",
        label: "ADRB2",
        metadata: {
          disease_gene_id: "GENE:000873",
          hgnc_id: "HGNC:286",
          ensembl_id: "ENSG00000169252",
          source: "opentargets",
        },
      },
      {
        id: "drug_target:TGT:000321",
        type: "drug_target",
        label: "Beta-2 adrenergic receptor",
        metadata: { drug_target_id: "TGT:000321", uniprot_id: "P07550", action_type: "AGONIST" },
      },
      {
        id: "pathway:R-HSA-390696",
        type: "pathway",
        label: "Adrenoceptors",
        metadata: { reactome_id: "R-HSA-390696" },
      },
    ],
    edges: [
      {
        id: "e1",
        source: "disease_gene:GENE:000873",
        target: "drug_target:TGT:000321",
        type: "matched_to",
        metadata: { hgnc_id: "HGNC:286" },
        provenance: "HGNC complete set overlap (Level 4)",
      },
      {
        id: "e2",
        source: "drug_target:TGT:000321",
        target: "pathway:R-HSA-390696",
        type: "participates_in",
        metadata: {},
        provenance: "reactome",
      },
    ],
    metadata: {
      graph_schema_version: "1.0",
      n_nodes: 5,
      n_edges: 2,
      n_candidates: 1,
      includes_ml_evidence: true,
      includes_explanation: false,
      node_type_counts: {},
      edge_type_counts: {},
      disclaimer: "not clinical",
      interpretation: "i",
    },
    ...overrides,
  };
}

describe("targetJoins", () => {
  it("projects each matched_to edge into both of its real endpoints", () => {
    const [join] = targetJoins(graph());

    expect(join.geneSymbol).toBe("ADRB2");
    expect(join.geneId).toBe("GENE:000873");
    expect(join.ensemblId).toBe("ENSG00000169252");
    expect(join.targetName).toBe("Beta-2 adrenergic receptor");
    expect(join.uniprotId).toBe("P07550");
    expect(join.actionType).toBe("AGONIST");
    // The identifier the join was actually made on, and how.
    expect(join.hgncId).toBe("HGNC:286");
    expect(join.provenance).toBe("HGNC complete set overlap (Level 4)");
  });

  it("yields nothing when the pair has no gene-target join", () => {
    const pathwayOnly = graph({ edges: [] });
    expect(targetJoins(pathwayOnly)).toEqual([]);
  });
});

describe("sharedPathways", () => {
  it("returns the graph's pathway nodes with the provenance of their edges", () => {
    const [pathway] = sharedPathways(graph());

    expect(pathway.name).toBe("Adrenoceptors");
    expect(pathway.reactomeId).toBe("R-HSA-390696");
    expect(pathway.provenances).toEqual(["reactome"]);
  });

  it("never invents a pathway that is not in the graph", () => {
    const noPathways = graph({ nodes: graph().nodes.filter((n) => n.type !== "pathway") });
    expect(sharedPathways(noPathways)).toEqual([]);
  });
});
