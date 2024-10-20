from typing import Optional, Union

from fastapi import FastAPI, HTTPException, status

app = FastAPI()


@app.get("/all_patients", status_code=status.HTTP_200_OK, tags=["patients"])
def get_all_clients():

    return HTTPException(
        status_code=status.HTTP_200_OK,
        detail={
            "error": 0,
            "msg": "success",
            "data": [
                {
                    "id": 1,
                    "q": 22,
                }
            ],
        },
    )


@app.get("/patientBy/{id}", status_code=status.HTTP_200_OK, tags=["patients"])
def get_patients_by_id(item_id: int, q: Union[str, None] = None):
    if q is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": 1,
                "msg": "faild",
                "data": [
                    {
                        "id": item_id,
                        "q": None,
                    }
                ],
            },
        )
    return HTTPException(
        status_code=status.HTTP_200_OK,
        detail={
            "error": 0,
            "msg": "success",
            "data": [
                {
                    "id": item_id,
                    "q": q,
                }
            ],
        },
    )
