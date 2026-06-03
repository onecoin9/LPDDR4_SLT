using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.BLL.Policy;

namespace Hsg.BLL
{
    public class PolicyManager
    {
        public PolicyFile Policy { private set; get; }
        //public  PolicyBase Policy;
        public static PolicyManager Instance = new PolicyManager();
        private PolicyManager()
        {

        }
        public void LoadPolicy(PolicyFile policy)
        {
            Policy = policy;
        }
        public PolicyMember GetPolicyMember(int index)
        {
            if (Policy == null || index >= Policy.MemberList.Count || index < 0)
            {
                return null;
            }
            return Policy.MemberList[index];
        }
        public TestBoardConfig LoadTestConfig(int index)
        {
            if (Policy == null || index >= Policy.MemberList.Count || index < 0)
            {
                return null;
            }
            PolicyCfgBase policy = PolicyConfig.LoadPolicyFile(Policy.MemberList[index].param.CfgFileName, Policy.MemberList[index].cfgFileBytes);
            if(policy != null)
            {
                byte[] configData = new byte[0];
                policy.ReadEmiContent(ref configData);
                TestBoardConfig cfg = new TestBoardConfig(configData);
                return cfg;
            }
            return null;
        }
    }
}
