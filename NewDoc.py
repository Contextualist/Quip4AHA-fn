from quip4aha import week, q4a, template, InvalidOperation

class NewDoc(object):

    def __init__(self):
        NextWednesday = week.RecentWeekDay('next Wednesday')
        self.NextWednesdayN = NextWednesday.strftime("%m%d")
        self.NextWednesdayS = NextWednesday.strftime("%B %d").replace(" 0", " ")
        self.ctx = ""
        self.client = q4a

    def do(self):
        #template = urllib2.urlopen("https://gist.githubusercontent.com/Contextualist"
        #                           "/e323408bf80ea76ab6125b6522d9a363/raw").read()
        # Pastebin (http://pastebin.com/raw/3cLgvDXe) is walled :(
        # Although Gist is also walled, Gist raw works fine :)
        # In the template, &#8203; (or &#x200b;) stands for a place-holder for a blank <p>.

        self.ctx = template.format(NextWednesdayS=self.NextWednesdayS)
        
        try:
            _ = self.client.latest_script_id
        except InvalidOperation as e:
            if e.code == 409:
                raise e # redundancy error
            #else: pass # script not found
        else:
            raise InvalidOperation("Redundancy Warning: The script has already been created.")
        
        self.client.new_document(content=self.ctx, format="html", title=self.NextWednesdayN, member_ids=[self.client.AHABC_ID])
        return "Done!"

if __name__=="__main__":
    NewDocAction = NewDoc()
    NewDocAction.do()
