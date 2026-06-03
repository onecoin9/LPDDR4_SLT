using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.ViewModel
{
    public interface IDutsMgrViewModel
    {
        TestStage Stage { get; set; }

        ObservableArray<TestStage> DutStates { get; set; }
    }
}
