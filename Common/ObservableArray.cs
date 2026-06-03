using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.Common
{
    /// <summary>
    /// 一个数组，可以绑定检测成员的改变
    /// </summary>
    /// <typeparam name="T"></typeparam>
    public class ObservableArray<T>
    {
        private T[] _array;
        private object _obj;
        public Action<int, object> OnArrayChange;
        public ObservableArray(T[] initialArray, object param = null)
        {
            _array = initialArray;
            _obj = param;
        }
        public T this[int index]
        {
            get
            {
                return _array[index];
            }
            set
            {
                // 在这里加入你的检查逻辑
                if (!_array[index].Equals(value))
                {
                    _array[index] = value;
                    OnArrayChange?.Invoke(index, _obj);
                }
            }
        }
        public int Length => _array.Length;
    }
}
