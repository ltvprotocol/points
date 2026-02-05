import src.aggregate_daily_points
import src.daily_states_v2
import src.daily_points_v2
import src.find_deployment_blocks
import src.find_daily_blocks
import src.nft_events
import src.pilot_vault_events
import test.main_test
from src.copy_last import copy_last

if __name__ == "__main__":
    src.find_deployment_blocks.main()
    src.find_daily_blocks.main()
    src.nft_events.main()
    src.pilot_vault_events.main()
    src.daily_states_v2.process_daily_states()
    
    src.daily_points_v2.process_points()
    src.aggregate_daily_points.aggregate_daily_points()
    test.main_test.run_all_tests()
    copy_last()