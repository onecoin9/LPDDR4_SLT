using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.Common
{
    public interface IHsgLogger
    {
        void Debug(string msg);
        void Info(string msg);
        void Warning(string msg);
        void Error(string msg);
        void Error(string msg, Exception ex);
    }
}
