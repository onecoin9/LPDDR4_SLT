using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.Remoting.Messaging;
using System.Text;
using System.Threading.Tasks;
using Hsg.BLL.Policy;

namespace Hsg.BLL
{
    /// <summary>
    ///  策略的配置文件管理
    /// </summary>
    public  class PolicyConfig
    {
      //  public  PolicyBase Policy;
        public static PolicyConfig Instance = new PolicyConfig();
        public static  PolicyCfgBase LoadPolicyFile(string filePath)
        {
            if (CommonPolicy.CheckFileName(filePath))
            {
                PolicyCfgBase policy = CommonPolicy.LoadFile(filePath);
                if (policy != null)
                {
                    return policy;
                }
            }//else if (SqlitePolicy.CheckFileName(filePath))
             //{
             //    Policy = SqlitePolicy.LoadFile(filePath);
             //    if (Policy != null)
             //    {
             //        return true;
             //    }
             //}
            return null;
        }
        public bool CheckPolicyFileIsEncry(string fileName)
        {
           // 待实现加密
            return false;
        }
        public static string GetPolicyFileFilter(bool encry)
        {
            if (encry)//代实现加密
            {
                return null;
            }
            else
            {
                return CommonPolicy.GetFileFilter();
            }
        }
        public static string GetPolicyFileFilter()
        {// 待增加加密文件
            string commmonExt = CommonPolicy.GetExtName();
            return $"cfg配置文件|*{commmonExt}";
        }

        public static PolicyCfgBase LoadPolicyFile(string fileName, byte[] fileBytes)
        {
            if (CommonPolicy.CheckFileName(fileName))
            {
                PolicyCfgBase policy = CommonPolicy.LoadFile(fileBytes, fileName);
                if (policy != null)
                {
                    return policy;
                }
            }//else if (SqlitePolicy.CheckFileName(filePath))
             //{
             //    Policy = SqlitePolicy.LoadFile(filePath);
             //    if (Policy != null)
             //    {
             //        return true;
             //    }
             //}
            return null;
        }
    }
}
