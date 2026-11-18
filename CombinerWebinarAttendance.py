from datetime import date, datetime, time, timedelta
from io import BytesIO
import glob
import io
import os
import re
import tempfile
import warnings
from math import floor
import pandas as pd
from stqdm import stqdm
import streamlit as st



# @title
def getNumber(number):
    try:
        mobile =  re.findall(r'\d+', str(number))[0]
        if len(mobile) == 11 and mobile[0] == "0":
            return "91"+str(mobile[1:])
        elif len(mobile)==10:
            return "91"+str(mobile)
            #return str(mobile)
        else:
            return str(mobile)
    except:
        return pd.NA

def getCleanPhone(number):
    try:
      return  re.findall(r'\d+', str(number))[0]
    except:
      return pd.NA

def getAttendanceFormat(filePath, AttendanceTimeThreshold = 0):

    fileName = filePath.split(".")[0].replace("attendee_", "")
    MaxSessionDuration = None
    TopicName = None
    try:
        Sessiondetails = pd.read_csv(filePath, sep=",", index_col=False, skiprows=2, nrows = 1)
        MaxSessionDuration = Sessiondetails["Actual Duration (minutes)"][0]
        TopicName = Sessiondetails["Topic"][0]
        WebinarID = Sessiondetails["Webinar ID"][0]
    except:
        print(filePath)

    try:
        Sessiondetails = pd.read_csv(filePath, sep=",", index_col=False, skiprows=5, nrows = 1)
        ZoomAccount = Sessiondetails["Email"][0]
    except:
        print(filePath)

    #While loop for reading the file untill the parser error is not encountered.
    cnt = 0
    while cnt != None:
        try:
            attendance = pd.read_csv(filePath, sep="," , index_col=False ,  skiprows=cnt )

            cnt = None
        except:
            cnt = cnt+1


    #st.write(filePath)
    #drops all the join time rows which are blank.
    attendance = attendance[(attendance["Join Time"] != "--")].dropna(subset=["Join Time"])
    print(WebinarID)
    #drops all the irrelevant rows
    attendance = attendance.where(lambda x : x["Attended"] == "Yes", other=pd.NA).dropna(subset=["Attended"])

    #Change the datatype of Join Time and Leave Time
    try:
        attendance[["Join Time", "Leave Time"]] = attendance.loc[:, ["Join Time", "Leave Time"]].map(lambda x : pd.to_datetime(x, format="%m/%d/%Y %I:%M:%S %p"))
    except:
        attendance[["Join Time", "Leave Time"]] = attendance.loc[:, ["Join Time", "Leave Time"]].map(lambda x : pd.to_datetime(x, format="%d/%m/%y %I:%M:%S %p", dayfirst=True))

    attendanceDate = attendance["Join Time"].dt.date.unique()[0]

    fileNamePart = attendance["Join Time"].dt.strftime("%d%b%Y").unique()[0]

    #Extracts only the digits from the Phone column
    attendance["Phone"] = attendance.Phone.map(lambda x: getCleanPhone(x))

    attendance["Phone Number"] = attendance["Phone"].map(lambda x: getNumber(x))

    #Change the datatype to float for the Time in session column
    attendance["Time in Session (minutes)"] = attendance["Time in Session (minutes)"].fillna(0).astype(float, errors="ignore")

    attendance["WebinarID"] = float(WebinarID.replace(" ", ""))
    #Group by using Email to get the total duration for that user
    Duration  = attendance[["Email", "Time in Session (minutes)"]].groupby(by="Email", as_index=False).agg( SessionDuration = ("Time in Session (minutes)", "sum") )

    #Drop the duplicate rows using the Email column
    cleanAttendance = attendance.drop_duplicates(subset="Email", keep="first").loc[:, ["Email", "Phone", "Phone Number", "WebinarID"]]

    #Merges the both the dataframe
    final = cleanAttendance.merge(Duration, how="left", left_on="Email", right_on="Email")

    #Change the datatype to float for the Phone column
    final.Phone = final.Phone.fillna(0).astype(float, errors="ignore")

    #Filters the data by the value mentioned in the AttendanceTimeThreshold threshold
    final = final[final["SessionDuration"] > AttendanceTimeThreshold]

    if MaxSessionDuration is not None:
        final["OptimizedSessionDuration"] = final["SessionDuration"].map(lambda x : float(x) if x<= MaxSessionDuration else MaxSessionDuration)

    final["MaxSessionDuration"] = MaxSessionDuration

    if TopicName is not None:
        final["TopicName"] = TopicName
    #Sorts the dataframe using the Time in session(minutes)
    final.sort_values(by="SessionDuration", ascending=False, inplace=True)

    final["Date"] = None
    final["Date"] = final["Date"].apply(lambda x: attendanceDate if x is None else x)

    final["ZoomAccount"] = ZoomAccount
    final.rename(columns = {"Email":"ZoomEmail", "Phone":"ZoomPhone"}, inplace=True)

    localFileSaveName = f"{fileNamePart}_{fileName}_Formatted.csv"
    outputFileName = f"attendee_{fileName}_Formatted.parquet"

    #final.to_csv(localFileSaveName, sep=",", index=False)

    #Saves the file to an excel file.
    # with pd.ExcelWriter(outputFileName, engine="openpyxl", mode="w") as f:
    #     final.to_excel(f, sheet_name="EligibleAttendee", index=False)
        #attendance.to_excel(f, sheet_name="OriginalSheet", index=False)

    final.to_parquet(outputFileName, compression="zstd",  index=False)
    #files.download(outputFileName) #Downloads the excel sheets

    #st.write(f"File downloaded {outputFileName}.")

    return outputFileName

def save_upload(fileupload):
    temp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(temp_dir, fileupload.name)          # no conversion: save the raw upload as-is
    with open(tmp_path, "wb") as f:                             # open the destination file in binary write mode
        f.write(fileupload.getvalue())                          # write the uploaded bytes to disk
    
    return tmp_path

st.header("Combine Webinar Attendance Files", divider=True, text_alignment="center")
st.set_page_config("CWA", layout="wide")
 

filePaths = st.file_uploader(label="Upload the Attendee Files", accept_multiple_files=True, type=["csv"])
concat_df = pd.DataFrame()

if filePaths:
    btn = st.button("Combine Files")
    if btn:
        for file in stqdm(filePaths):
            outputFileName = getAttendanceFormat(save_upload(file))
            st.text(outputFileName)
            df = pd.read_parquet(outputFileName)
            concat_df = pd.concat([concat_df,df], axis = "rows", ignore_index =True)

        buffer = io.BytesIO()
        FileDate = concat_df["Date"].unique()[0].date().strftime("%Y_%m_%d")
        concatFileName = f"Attendance_Formatted_{FileDate}.parquet"
        concat_df.to_parquet(buffer, index=False)

        st.download_button(
                label="Save MEGA file",
                data=buffer.getvalue(),
                file_name=concatFileName,
                mime = "application/vnd.apache.parquet",
                on_click="ignore"
            )
