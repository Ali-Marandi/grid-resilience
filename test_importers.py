import unittest

from grid_resilience_import import CIMCGMESImporter, IEECDFImporter


def fixed_line(fields):
    row = [" "] * 128
    for start, end, value in fields:
        text = str(value)
        row[start:end] = list(text[: end - start].rjust(end - start))
    return "".join(row)


class ImporterTests(unittest.TestCase):
    def test_ieee_cdf_imports_a_valid_ac_network_and_warns_about_opf_defaults(self):
        title = fixed_line([(31, 37, "100.0")])
        slack = fixed_line([
            (0, 4, 1), (6, 17, "GRID"), (19, 20, 1), (20, 23, 1), (24, 26, 3),
            (27, 33, "1.02"), (40, 49, "0"), (49, 59, "0"), (59, 67, "55"), (67, 75, "5"),
            (76, 83, "230"), (84, 90, "1.02"), (90, 98, "80"), (98, 106, "-80"),
        ])
        load = fixed_line([
            (0, 4, 2), (6, 17, "LOAD"), (19, 20, 1), (20, 23, 1), (24, 26, 0),
            (27, 33, "1.0"), (40, 49, "50"), (49, 59, "20"), (76, 83, "230"),
        ])
        branch = fixed_line([
            (0, 4, 1), (5, 9, 2), (16, 17, 1), (19, 29, "0.01"), (29, 40, "0.10"),
            (40, 50, "0.02"), (50, 55, "100"), (76, 82, "1.0"),
        ])
        content = "\n".join([title, "BUS DATA FOLLOWS", slack, load, "-999", "BRANCH DATA FOLLOWS", branch, "-999"])
        report = IEECDFImporter().parse(content, "tiny.cdf")
        self.assertTrue(report.ready_for_analysis)
        self.assertEqual(len(report.model.buses), 2)
        self.assertEqual(len(report.model.branches), 1)
        self.assertEqual(len(report.model.generators), 1)
        self.assertTrue(any(issue.code == "CDF_OPF_DEFAULTS" for issue in report.warnings))

    def test_cim_subset_builds_network_and_declares_non_conformance(self):
        xml = b'''<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:cim="urn:iec:cim">
  <cim:TopologicalNode rdf:ID="B1"><cim:IdentifiedObject.name>Grid</cim:IdentifiedObject.name></cim:TopologicalNode>
  <cim:TopologicalNode rdf:ID="B2"><cim:IdentifiedObject.name>Load</cim:IdentifiedObject.name></cim:TopologicalNode>
  <cim:ExternalNetworkInjection rdf:ID="G1"><cim:IdentifiedObject.name>External Grid</cim:IdentifiedObject.name><cim:RotatingMachine.p>60</cim:RotatingMachine.p></cim:ExternalNetworkInjection>
  <cim:EnergyConsumer rdf:ID="D1"><cim:EnergyConsumer.p>50</cim:EnergyConsumer.p><cim:EnergyConsumer.q>15</cim:EnergyConsumer.q></cim:EnergyConsumer>
  <cim:ACLineSegment rdf:ID="L1"><cim:ACLineSegment.r>0.01</cim:ACLineSegment.r><cim:ACLineSegment.x>0.1</cim:ACLineSegment.x></cim:ACLineSegment>
  <cim:Terminal rdf:ID="T1"><cim:Terminal.ConductingEquipment rdf:resource="#G1"/><cim:Terminal.TopologicalNode rdf:resource="#B1"/></cim:Terminal>
  <cim:Terminal rdf:ID="T2"><cim:Terminal.ConductingEquipment rdf:resource="#D1"/><cim:Terminal.TopologicalNode rdf:resource="#B2"/></cim:Terminal>
  <cim:Terminal rdf:ID="T3"><cim:Terminal.ConductingEquipment rdf:resource="#L1"/><cim:Terminal.TopologicalNode rdf:resource="#B1"/></cim:Terminal>
  <cim:Terminal rdf:ID="T4"><cim:Terminal.ConductingEquipment rdf:resource="#L1"/><cim:Terminal.TopologicalNode rdf:resource="#B2"/></cim:Terminal>
</rdf:RDF>'''
        report = CIMCGMESImporter().parse_xml_documents([("EQ.xml", xml)], "tiny.zip")
        self.assertTrue(report.ready_for_analysis)
        self.assertEqual(len(report.model.buses), 2)
        self.assertEqual(len(report.model.branches), 1)
        self.assertEqual(report.model.slack_bus_id, "B1")
        self.assertTrue(any(issue.code == "CGMES_SUBSET" for issue in report.issues))


if __name__ == "__main__":
    unittest.main(verbosity=2)
