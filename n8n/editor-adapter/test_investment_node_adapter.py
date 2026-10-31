import unittest
from investment_node_adapter import execute_node01,execute_node02,node_binding,WF01_MODES

class InvestmentNodeAdapterTests(unittest.TestCase):
    def test_both_modes_n01_to_n02_passthrough(self):
        for workflow,kind in WF01_MODES.items():
            n1=execute_node01({"ui_selection":kind,"requested_detail_limit":1,"max_pages":2},workflow_kind=kind)
            n2=execute_node02(n1,workflow_kind=kind)
            for k,v in n1.items():self.assertEqual(n2[k],v)
            self.assertEqual(n2["page_size"],50)
            self.assertEqual(n2["selected_count"],0)
            self.assertEqual(node_binding(workflow,"wf01-"+kind+"-02")["python_function"],"execute_node02")
            self.assertEqual(execute_node02({**n1,"page_size":25},workflow_kind=kind)["page_size"],25)

    def test_fails_closed(self):
        for kind in ("strategy","library"):
            n=execute_node01({"ui_selection":kind,"requested_detail_limit":1},workflow_kind=kind)
            for bad in ({**n,"max_pages":20},{**n,"sort":"updated_desc"},
                        {**n,"kind":"wrong"},{**n,"page_size":0},
                        {**n,"selected_count":3}):
                with self.assertRaises(ValueError):
                    execute_node02(bad,workflow_kind=kind)
            for limit in (True,0,2):
                with self.assertRaises(ValueError):
                    execute_node01({"ui_selection":kind,"requested_detail_limit":limit},workflow_kind=kind)

if __name__=="__main__":unittest.main()
