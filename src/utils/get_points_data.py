import json
import datetime
from typing import List, Dict


class LpProgram:
    def __init__(self, balance: int, lp_start_date: datetime.date):
        self.balance = balance
        self.lp_start_date = lp_start_date


class UserLpSnapshot:
    def __init__(self, lp_programs: List[LpProgram]):
        self.lp_programs = lp_programs


type Address = str
type LpSnapshot = Dict[Address, UserLpSnapshot]


def get_points_data():
    with open("data/lp_snapshot.json", "r") as f:
        raw = json.load(f)
    points_program_start_block = raw["points_program_start_block"]
    lp_snapshot = {
        address.lower(): UserLpSnapshot(
            [
                LpProgram(
                    program["balance"], datetime.date.fromisoformat(program["lp_start_date"])
                )
                for program in lp_programs
            ]
        )
        for address, lp_programs in raw["snapshot"].items()
    }
    return points_program_start_block, lp_snapshot
