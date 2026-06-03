using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Test
{
    public enum Event
    {
        Event_INI,
        Event1,
        Event2,
        Event3
    }
    public enum State
    {
        STATE_INI,
        STATE_1,
        STATE_2,
        STATE_3
    }
    class StateDemo : StateMechine<State, Event>
    {
        //private IHsgLogger _logger;
        public StateDemo(IHsgLogger logger) : base("StateDemo", logger)
        {
            _logger = logger;
            RegistEvent();
        }
        public void RegistEvent()
        {
            RegisterStateHandle(State.STATE_INI, Event.Event_INI, EventHandleInit);
            RegisterStateHandle(State.STATE_1, Event.Event1, EventHandle1);
            RegisterStateHandle(State.STATE_1, Event.Event2, EventHandle2);
            RegisterStateHandle(State.STATE_1, Event.Event3, EventHandle3);

            RegisterStateHandle(State.STATE_2, Event.Event1, EventHandle1);
            RegisterStateHandle(State.STATE_2, Event.Event2, EventHandle2);
            RegisterStateHandle(State.STATE_2, Event.Event3, EventHandle3);

            RegisterStateHandle(State.STATE_3, Event.Event1, EventHandle1);
            RegisterStateHandle(State.STATE_3, Event.Event2, EventHandle2);
            RegisterStateHandle(State.STATE_3, Event.Event3, EventHandle3);
        }

        public State EventHandleInit(Object param)
        {
             Task.Delay(1000).Wait(); ;
            return State.STATE_1;
        }
        public State EventHandle1(Object param)
        {
             Task.Delay(1000).Wait();
            return State.STATE_1;
        }
        public State EventHandle2(Object param)
        {
             Task.Delay(1000).Wait(); ;
            return State.STATE_2;
        }
        public State EventHandle3(Object param)
        {
             Task.Delay(1000).Wait(); ;
            return State.STATE_3;
        }
        protected override void NotifyStateChange(State state)
        {
            _logger.Info("new state:" + state);
        }

        public override void Run()
        {
            start(State.STATE_INI);
        }




        //internal void PostEvent(Event event1, object value)
        //{
        //    throw new NotImplementedException();
        //}
    }
}
